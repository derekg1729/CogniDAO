from pathlib import Path # For memory bank root
from typing import Any, Dict

from dotenv import load_dotenv
# Comment out Prefect imports
# from prefect import flow, task, get_run_logger
from langchain_core.memory import BaseMemory
from langchain_core.messages import HumanMessage
# Removed LangChain LLM/Runnable/Prompt imports
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
# from langchain_core.runnables import RunnableSequence
# from langchain_core.output_parsers import StrOutputParser
# from langchain_openai import ChatOpenAI

# Import from existing handler
from infra_core.openai_handler import initialize_openai_client, create_completion, extract_content

# Import the new memory classes
from .cogni_memory_bank import CogniMemoryBank, CogniLangchainMemoryAdapter

# Load environment variables (for OPENAI_API_KEY needed by the handler)
load_dotenv()

# --- Removed MockFileMemory class definition --- 
# class MockFileMemory(BaseMemory): ... (delete this entire class)

# --- Prefect Tasks --- 

# Comment out @task decorator
# @task
def agent_task(agent_name: str, system_prompt: str, input_data: Dict[str, Any], memory: BaseMemory, input_key: str = "input"):
    """Generic function to run an agent using infra_core.openai_handler."""
    # logger = get_run_logger()
    print(f"Running {agent_name} with input: {input_data}") # Use print instead of logger

    # Initialize OpenAI client using the handler task
    # Note: This runs the task within the task. Consider initializing once in the flow if performance matters.
    openai_client = initialize_openai_client.fn() # Use .fn() to call underlying function directly

    # Load history from memory
    memory_vars = memory.load_memory_variables({}) # receives {"history": [BaseMessage, ...]}
    history_messages = memory_vars.get("history", [])
    # logger.info(f"{agent_name} loaded {len(history_messages)} messages from history.")
    print(f"{agent_name} loaded {len(history_messages)} messages from history.")

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

    # logger.info(f"{agent_name} constructed user prompt: '{full_user_prompt[:200]}...'") # Log truncated prompt
    print(f"{agent_name} constructed user prompt: '{full_user_prompt[:200]}...'")

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
        # logger.info(f"{agent_name} received completion response.")
        print(f"{agent_name} received completion response.")

        # Extract the content using the handler task's function
        response = extract_content.fn(completion_response)
        # logger.info(f"{agent_name} extracted response: {response}")
        print(f"{agent_name} extracted response: {response}")

    except Exception as e:
        # logger.error(f"{agent_name} failed during OpenAI call: {e}")
        print(f"ERROR: {agent_name} failed during OpenAI call: {e}")
        response = f"Error: Could not get response from AI. Details: {e}"

    # Save context back to memory
    memory.save_context(input_data, {"output": response})
    # logger.info(f"{agent_name} saved context.")
    print(f"{agent_name} saved context.")

    return response

# --- Prefect Flow (now just a regular function) --- 

# Comment out @flow decorator
# @flow(name="MVP 2-Agent CogniMemoryBank Workflow") # Updated flow name
def two_agent_flow():
    """Demonstrates two agents interacting via shared CogniMemoryBank."""
    # logger = get_run_logger()
    print("Starting two_agent_flow...") # Use print

    # Define Memory Bank Configuration
    memory_root = Path("./_memory_banks_experiment") # Define root directory for this experiment's banks
    project = "mvp_flow_test"
    # Session ID will be generated automatically by CogniMemoryBank

    # Ensure root exists
    memory_root.mkdir(exist_ok=True)
    # logger.info(f"Using memory bank root: {memory_root.resolve()}")
    print(f"Using memory bank root: {memory_root.resolve()}")

    # Initialize the core memory bank first
    core_memory_bank = CogniMemoryBank(memory_bank_root=memory_root, project_name=project)
    session_path = core_memory_bank._get_session_path() # Get the generated session path for logging
    # logger.info(f"Initialized CogniMemoryBank core for project '{project}', session: {core_memory_bank.session_id}")
    # logger.info(f"Session path: {session_path}")
    print(f"Initialized CogniMemoryBank core for project '{project}', session: {core_memory_bank.session_id}")
    print(f"Session path: {session_path}")

    # Create the LangChain adapter, wrapping the core bank
    shared_memory_adapter = CogniLangchainMemoryAdapter(memory_bank=core_memory_bank)

    # Clear the session via the adapter (which calls core_memory_bank.clear_session())
    shared_memory_adapter.clear()
    # logger.info(f"Cleared session {core_memory_bank.session_id} via adapter.")
    print(f"Cleared session {core_memory_bank.session_id} via adapter.")

    # Define System Prompts
    agent_1_system_prompt = "You are Agent 1. Your job is to receive a fact and state clearly that you have recorded it. Only state that you recorded it."
    agent_2_system_prompt = "You are Agent 2. Answer the user's question based *only* on the provided Conversation History. If the answer is not in the history, say you don't know."

    # Agent 1 introduces a fact
    fact_to_introduce = "The project uses CogniMemoryBank for state management."
    agent_1_input = {"input": fact_to_introduce}
    # Run Agent 1 task - change .submit to direct call
    agent_task(
        agent_name="Agent 1 (Fact Recorder)",
        system_prompt=agent_1_system_prompt,
        input_data=agent_1_input,
        memory=shared_memory_adapter, # Pass the adapter instance
        input_key="input"
    )

    # Agent 2 asks a question that requires the fact
    question = "What component manages state in this project?"
    agent_2_input = {"input": question}
    # Run Agent 2 task - change .submit to direct call, remove wait_for
    agent_2_result = agent_task(
        agent_name="Agent 2 (Question Answerer)",
        system_prompt=agent_2_system_prompt,
        input_data=agent_2_input,
        memory=shared_memory_adapter, # Pass the adapter instance
        input_key="input"
        # wait_for=[agent_1_result] # Remove wait_for
    )

    # Get result directly from variable
    final_response = agent_2_result
    # logger.info(f"Final response from Agent 2: {final_response}")
    print(f"Final response from Agent 2: {final_response}")

    # Keep session files for inspection
    # logger.info(f"Flow completed. Memory session files kept for inspection: {session_path}")
    print(f"Flow completed. Memory session files kept for inspection: {session_path}")


if __name__ == "__main__":
    two_agent_flow() 