import os
import json
import tempfile
from typing import Any, Dict, List

from dotenv import load_dotenv
from prefect import flow, task, get_run_logger
from langchain_core.memory import BaseMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
# Removed LangChain LLM/Runnable/Prompt imports
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_core.runnables import RunnableSequence
# from langchain_core.output_parsers import StrOutputParser
# from langchain_openai import ChatOpenAI

# Import from existing handler
from infra_core.openai_handler import initialize_openai_client, create_completion, extract_content

# Load environment variables (for OPENAI_API_KEY needed by the handler)
load_dotenv()

# Mock Memory Implementation (using a temporary JSON file)
class MockFileMemory(BaseMemory):
    """Mock memory class using a temporary JSON file for persistence."""
    file_path: str # Declare file_path as a field

    def __init__(self, file_path: str):
        # Pass file_path up to the parent initializer
        super().__init__(file_path=file_path)
        # Initialize file if it doesn't exist
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"history": []}, f)

    @property
    def memory_variables(self) -> List[str]:
        # We only use history
        return ["history"]

    def _load_memory_data(self) -> Dict[str, List[BaseMessage]]:
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                # Deserialize messages
                history_raw = data.get("history", [])
                history = []
                for msg_data in history_raw:
                    if msg_data.get("type") == "human":
                        history.append(HumanMessage(content=msg_data["content"]))
                    elif msg_data.get("type") == "ai":
                        history.append(AIMessage(content=msg_data["content"]))
                    elif msg_data.get("type") == "system": # Handle system messages if needed
                         history.append(SystemMessage(content=msg_data["content"]))
                return {"history": history}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"history": []}

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # In this simple mock, we ignore inputs and just load the history.
        return self._load_memory_data()


    def _save_memory_data(self, data: Dict[str, List[BaseMessage]]):
        # Serialize messages
        history_serializable = []
        for msg in data.get("history", []):
            if isinstance(msg, HumanMessage):
                history_serializable.append({"type": "human", "content": msg.content})
            elif isinstance(msg, AIMessage):
                history_serializable.append({"type": "ai", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                 history_serializable.append({"type": "system", "content": msg.content})

        with open(self.file_path, 'w') as f:
            json.dump({"history": history_serializable}, f, indent=2)


    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context from this conversation to buffer."""
        # Assumes inputs has a single key for the human message
        input_key = list(inputs.keys())[0]
        input_str = inputs[input_key]
        # Assumes outputs has a single key for the AI message
        output_key = list(outputs.keys())[0]
        output_str = outputs[output_key]
        current_memory = self._load_memory_data()
        history = current_memory.get("history", [])
        history.append(HumanMessage(content=input_str))
        history.append(AIMessage(content=output_str))
        self._save_memory_data({"history": history})


    def clear(self) -> None:
        """Clear memory contents."""
        with open(self.file_path, 'w') as f:
            json.dump({"history": []}, f)

# --- Removed LangChain Global Components --- 
# llm = ...
# agent_1_prompt = ...
# agent_1_runnable = ...
# agent_2_prompt = ...
# agent_2_runnable = ...

# --- Prefect Tasks --- 

@task
def agent_task(agent_name: str, system_prompt: str, input_data: Dict[str, Any], memory: BaseMemory, input_key: str = "input"):
    """Generic Prefect task to run an agent using infra_core.openai_handler."""
    logger = get_run_logger()
    logger.info(f"Running {agent_name} with input: {input_data}")

    # Initialize OpenAI client using the handler task
    # Note: This runs the task within the task. Consider initializing once in the flow if performance matters.
    openai_client = initialize_openai_client.fn() # Use .fn() to call underlying function directly

    # Load history from memory
    memory_vars = memory.load_memory_variables({}) # receives {"history": [BaseMessage, ...]}
    history_messages = memory_vars.get("history", [])
    logger.info(f"{agent_name} loaded {len(history_messages)} messages from history.")

    # Construct the user prompt
    user_input = input_data[input_key]
    full_user_prompt = f"{user_input}"

    # For Agent 2 (or any agent needing history), prepend history to the user prompt
    if history_messages:
        history_str = "\n\nConversation History:\n"
        for msg in history_messages:
            prefix = "Human" if isinstance(msg, HumanMessage) else "AI"
            history_str += f"{prefix}: {msg.content}\n"
        # Prepend history to the *current* user input for the prompt
        full_user_prompt = f"{history_str}\nHuman: {user_input}"

    logger.info(f"{agent_name} constructed user prompt: '{full_user_prompt[:200]}...'") # Log truncated prompt

    # Call the completion task from the handler
    # Using .fn() to call the underlying function directly to avoid Prefect overhead/complexity here
    # Note: create_completion is also a Prefect task, calling .fn() bypasses task runner behavior
    try:
        completion_response = create_completion.fn(
            client=openai_client,
            system_message=system_prompt,
            user_prompt=full_user_prompt,
            model="gpt-3.5-turbo", # Keep model consistent
            temperature=0 # Keep temp consistent
        )
        logger.info(f"{agent_name} received completion response.")

        # Extract the content using the handler task's function
        response = extract_content.fn(completion_response)
        logger.info(f"{agent_name} extracted response: {response}")

    except Exception as e:
        logger.error(f"{agent_name} failed during OpenAI call: {e}")
        response = f"Error: Could not get response from AI. Details: {e}"

    # Save context back to memory
    memory.save_context(input_data, {"output": response})
    logger.info(f"{agent_name} saved context.")

    return response

# --- Prefect Flow --- 

@flow(name="MVP 2-Agent OpenAI Handler Workflow")
def two_agent_flow():
    """Demonstrates two agents interacting via shared mock memory using openai_handler."""
    logger = get_run_logger()
    temp_dir = tempfile.mkdtemp()
    memory_file_path = os.path.join(temp_dir, "memory.json")
    logger.info(f"Using temporary memory file: {memory_file_path}")

    # Initialize shared memory
    shared_memory = MockFileMemory(file_path=memory_file_path)
    shared_memory.clear() # Ensure clean state

    # Define System Prompts
    agent_1_system_prompt = "You are Agent 1. Your job is to receive a fact and state clearly that you have recorded it. Only state that you recorded it."
    agent_2_system_prompt = "You are Agent 2. Answer the user's question based *only* on the provided Conversation History. If the answer is not in the history, say you don't know."

    # Agent 1 introduces a fact
    fact_to_introduce = "The project uses LangChain memory components for state management."
    agent_1_input = {"input": fact_to_introduce}
    # Run Agent 1 task
    agent_1_result = agent_task.submit(
        agent_name="Agent 1 (Fact Recorder)",
        system_prompt=agent_1_system_prompt,
        input_data=agent_1_input,
        memory=shared_memory,
        input_key="input"
    )

    # Agent 2 asks a question that requires the fact
    question = "What technology manages state in this project?"
    agent_2_input = {"input": question}
    # Run Agent 2 task, ensuring it waits for Agent 1
    agent_2_result = agent_task.submit(
        agent_name="Agent 2 (Question Answerer)",
        system_prompt=agent_2_system_prompt,
        input_data=agent_2_input,
        memory=shared_memory,
        input_key="input",
        wait_for=[agent_1_result] # Ensure Agent 1 finishes first
    )

    final_response = agent_2_result.result()
    logger.info(f"Final response from Agent 2: {final_response}")

    # Clean up the temporary directory and file
    # import shutil # Uncomment if you want cleanup
    # shutil.rmtree(temp_dir)
    logger.info(f"Flow completed. Memory file kept for inspection: {memory_file_path}")


if __name__ == "__main__":
    two_agent_flow() 