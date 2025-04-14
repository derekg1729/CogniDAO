import sys
import os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from prefect import task, flow, get_run_logger
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any # Added Any

# --- Project Constants Import ---
from infra_core.constants import MEMORY_BANKS_ROOT, THOUGHTS_DIR, BASE_DIR

# --- Memory Imports ---
from infra_core.memory.memory_bank import CogniMemoryBank, CogniLangchainMemoryAdapter

# --- Agent Imports ---
from infra_core.cogni_agents.core_cogni import CoreCogniAgent
from infra_core.cogni_agents.reflection_cogni import ReflectionCogniAgent

def write_thought_file(ai_content):
    """
    Write the thought content to a file with proper formatting. Tagged as #thought for logseq
    
    Args:
        ai_content (str): The AI-generated thought content
        
    Returns:
        tuple: (timestamp, filepath) - timestamp string and path to the created file
    """
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    
    # Create the full content with timestamp and tags
    content = f"tags:: #thought\n\n# Thought {timestamp}\n\n{ai_content}\n\nTime: {now.isoformat()}\n"
    
    # Save to file
    filepath = os.path.join(THOUGHTS_DIR, f"{timestamp}.md")
    os.makedirs(THOUGHTS_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
        
    return timestamp, filepath

@task
def create_initial_thought(memory_adapter: CogniLangchainMemoryAdapter) -> Dict[str, Any]:
    """
    Creates the initial thought using CoreCogniAgent and saves context to shared memory.
    """
    logger = get_run_logger()
    
    try:
        logger.info("Creating initial thought...")
        # Use imported THOUGHTS_DIR and BASE_DIR
        agent_root = Path(THOUGHTS_DIR)
        
        # CoreCogniAgent doesn't take adapter in init, uses base class logic for memory bank
        # path construction if needed directly (e.g. during load_spirit/context fallback)
        core_cogni = CoreCogniAgent(
            agent_root=agent_root,
            # Pass None when using mock memory, as it doesn't use the root path
            memory_bank_root_override=None, 
            project_root_override=Path(BASE_DIR) # Use imported BASE_DIR
        )
        # Replace agent's internal memory with the shared one from the flow
        core_cogni.memory = memory_adapter.memory_bank
        
        prepared_input = core_cogni.prepare_input()
        # Get the prompt used for saving context
        initial_prompt = prepared_input.get("prompt", "Generate initial thought.")
        
        # Act returns the result dictionary without saving internally
        result_data = core_cogni.act(prepared_input)
        initial_thought = result_data.get("thought_content", "[No thought content]")

        # Save context using the LangChain adapter pattern
        memory_adapter.save_context(inputs={"input": initial_prompt}, outputs={"output": initial_thought})
        logger.info("Saved initial thought context to history via adapter.")

        # Optional: Log detailed action using record_action (writes action_*.md, decisions.jsonl)
        try:
            core_cogni.record_action(result_data, prefix="thought_")
            logger.info("Logged detailed initial thought action via record_action.")
        except Exception as e:
            logger.warning(f"Could not log detailed action for initial thought: {e}")

        logger.info(f"INITIAL THOUGHT OUTPUT: {initial_thought}")
        return result_data
        
    except Exception as e:
        logger.error(f"Error in initial thought generation: {e}")
        # Return error structure
        return {"error": str(e)}

@task
def create_reflection_thought(memory_adapter: CogniLangchainMemoryAdapter) -> Dict[str, Any]:
    """
    Creates a reflection thought using ReflectionCogniAgent based on shared memory history.
    """
    logger = get_run_logger()

    try:
        logger.info("Creating reflection thought...")
        # Use imported THOUGHTS_DIR and BASE_DIR
        agent_root = Path(THOUGHTS_DIR)
        
        # ReflectionCogniAgent takes the adapter instance in init
        reflection_cogni = ReflectionCogniAgent(
            agent_root=agent_root,
            memory_adapter=memory_adapter, 
            # Pass None when using mock memory
            memory_bank_root_override=None,
            project_root_override=Path(BASE_DIR) # Use imported BASE_DIR
        )
        # Replace agent's internal memory with the shared one from the flow
        reflection_cogni.memory = memory_adapter.memory_bank
        
        prepared_input = reflection_cogni.prepare_input()
        # Get the prompt used for saving context
        reflection_prompt = prepared_input.get("prompt", "Generate reflection.")

        # Act returns the result dictionary without saving internally
        result_data = reflection_cogni.act(prepared_input)
        reflection = result_data.get("reflection_content", "[No reflection content]")

        # Save context using the LangChain adapter pattern
        memory_adapter.save_context(inputs={"input": reflection_prompt}, outputs={"output": reflection})
        logger.info("Saved reflection context to history via adapter.")

        # Optional: Log detailed action using record_action
        try:
            reflection_cogni.record_action(result_data, prefix="reflection_")
            logger.info("Logged detailed reflection action via record_action.")
        except Exception as e:
            logger.warning(f"Could not log detailed action for reflection: {e}")

        logger.info(f"REFLECTION OUTPUT: {reflection}")
        return result_data

    except Exception as e:
        logger.error(f"Error in reflection generation: {e}")
        return {"error": str(e)}


@flow
def ritual_of_presence_flow():
    """Flow that generates an initial thought and a reflection using shared memory."""
    logger = get_run_logger()
    logger.info("Starting dual-agent Ritual of Presence flow...")

    # --- Initialize Shared Memory ---
    project_name = "ritual_of_presence"
    # Use imported MEMORY_BANKS_ROOT
    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)
    
    fixed_session_id = "ritual-session" # Define a constant session ID
    core_memory_bank = CogniMemoryBank(
        memory_bank_root=memory_root, 
        project_name=project_name,
        session_id=fixed_session_id # Pass the fixed session ID
    )
    shared_memory_adapter = CogniLangchainMemoryAdapter(memory_bank=core_memory_bank)
    session_id = core_memory_bank.session_id # This will now be "ritual-session"
    session_path = core_memory_bank._get_session_path()
    logger.info(f"Initialized shared memory for project '{project_name}', session '{session_id}' at {session_path}")

    # Clear any previous state for this session ID (optional, good for clean runs)
    # shared_memory_adapter.clear() # Commented out to allow persistence
    # logger.info("Cleared previous memory session state (if any). ") # Commented out log message

    # --- Run Agent Tasks Sequentially ---
    initial_result = create_initial_thought(memory_adapter=shared_memory_adapter)
    
    if "error" in initial_result:
        logger.error("Flow aborted due to error in initial thought generation.")
        return f"Flow failed during initial thought: {initial_result['error']}"

    # Pass the shared adapter; Reflection agent reads history via adapter
    reflection_result = create_reflection_thought(memory_adapter=shared_memory_adapter)

    if "error" in reflection_result:
        logger.error("Flow completed with error in reflection generation.")
        return f"Flow completed with error during reflection: {reflection_result['error']}"
    
    logger.info("Dual-agent Ritual of Presence flow completed successfully.")
    return f"Ritual of Presence completed. Session: {session_id}. See logs and memory bank: {session_path}"

if __name__ == "__main__":
    # Run the updated ritual of presence
    result_message = ritual_of_presence_flow()
    print(result_message)
