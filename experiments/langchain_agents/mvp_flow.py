import os
import json
import tempfile
from typing import Any, Dict, List

from prefect import flow, task, get_run_logger
from langchain_core.memory import BaseMemory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


# Placeholder for LangChain Agent - will be replaced with actual agents later
def run_agent(agent_name: str, input_text: str, memory: BaseMemory) -> str:
    """Simulates running a LangChain agent."""
    logger = get_run_logger()
    logger.info(f"Running {agent_name} with input: '{input_text}'")

    # Simulate memory interaction
    memory_vars = memory.load_memory_variables({})
    logger.info(f"{agent_name} loaded memory variables: {memory_vars}")

    # Simulate agent logic based on name
    if agent_name == "Agent 1":
        response = f"Fact recorded: {input_text}"
        # Simulate saving context - Agent 1 adds a fact
        memory.save_context({"input": input_text}, {"output": "Fact recorded."})
        logger.info(f"{agent_name} saved context.")
    elif agent_name == "Agent 2":
        # Simulate recalling the fact - simplistic check
        history = memory_vars.get("history", [])
        recalled_fact = "Unknown"
        if history and isinstance(history[-1], AIMessage) and history[-1].content == "Fact recorded.":
             if isinstance(history[-2], HumanMessage):
                 recalled_fact = history[-2].content

        response = f"Based on memory, the fact is: {recalled_fact}"
        # Simulate saving context - Agent 2 responds
        memory.save_context({"input": input_text}, {"output": response})
        logger.info(f"{agent_name} saved context.")
    else:
        response = "Unknown agent."

    logger.info(f"{agent_name} response: {response}")
    return response

# Mock Memory Implementation (using a temporary JSON file)
class MockFileMemory(BaseMemory):
    """Mock memory class using a temporary JSON file for persistence."""
    file_path: str # Declare file_path as a field

    def __init__(self, file_path: str):
        # Pass file_path up to the parent initializer
        super().__init__(file_path=file_path)
        # self.file_path = file_path # No longer needed here as super() handles it
        # Initialize file if it doesn't exist
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"history": []}, f)

    @property
    def memory_variables(self) -> List[str]:
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
                return {"history": history}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"history": []}

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
         # In this simple mock, we ignore inputs and just load the history
        return self._load_memory_data()


    def _save_memory_data(self, data: Dict[str, List[BaseMessage]]):
         # Serialize messages
        history_serializable = []
        for msg in data.get("history", []):
             if isinstance(msg, HumanMessage):
                 history_serializable.append({"type": "human", "content": msg.content})
             elif isinstance(msg, AIMessage):
                 history_serializable.append({"type": "ai", "content": msg.content})

        with open(self.file_path, 'w') as f:
             json.dump({"history": history_serializable}, f, indent=2)


    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save context from this conversation to buffer."""
        input_str = inputs.get("input", "")
        output_str = outputs.get("output", "")
        current_memory = self._load_memory_data()
        history = current_memory.get("history", [])
        history.append(HumanMessage(content=input_str))
        history.append(AIMessage(content=output_str))
        self._save_memory_data({"history": history})


    def clear(self) -> None:
        """Clear memory contents."""
        with open(self.file_path, 'w') as f:
            json.dump({"history": []}, f)


@task
def agent_1_task(fact: str, memory: BaseMemory):
    """Prefect task for Agent 1."""
    return run_agent("Agent 1", fact, memory)

@task
def agent_2_task(question: str, memory: BaseMemory):
    """Prefect task for Agent 2."""
    return run_agent("Agent 2", question, memory)

@flow(name="MVP 2-Agent Workflow")
def two_agent_flow():
    """Demonstrates two agents interacting via shared mock memory."""
    logger = get_run_logger()
    # Use a temporary file for this flow run
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".json", prefix="memory_") as temp_file:
        memory_file_path = temp_file.name
    logger.info(f"Using temporary memory file: {memory_file_path}")

    # Initialize shared memory
    shared_memory = MockFileMemory(file_path=memory_file_path)
    shared_memory.clear() # Ensure clean state

    # Agent 1 introduces a fact
    fact_to_introduce = "The project uses LangChain memory."
    agent_1_result = agent_1_task.submit(fact_to_introduce, shared_memory)

    # Agent 2 asks a question that requires the fact
    question = "What kind of memory is used in this project?"
    # Ensure Agent 2 runs after Agent 1 completes
    agent_2_result = agent_2_task.submit(question, shared_memory, wait_for=[agent_1_result])

    final_response = agent_2_result.result()
    logger.info(f"Final response from Agent 2: {final_response}")

    # Clean up the temporary file
    # os.remove(memory_file_path) # Keep file for inspection for now
    logger.info(f"Flow completed. Memory file kept for inspection: {memory_file_path}")


if __name__ == "__main__":
    two_agent_flow() 