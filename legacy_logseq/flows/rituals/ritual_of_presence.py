import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from prefect import task, flow, get_run_logger
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any, Optional
import json
import argparse
from prefect.blocks.system import Secret

# --- Project Constants Import ---
from legacy_logseq.constants import MEMORY_BANKS_ROOT, THOUGHTS_DIR, BASE_DIR

# --- Memory Imports ---
from legacy_logseq.memory.memory_bank import FileMemoryBank, CogniLangchainMemoryAdapter

# --- Agent Imports ---
from legacy_logseq.cogni_agents.core_cogni import CoreCogniAgent
from legacy_logseq.cogni_agents.swarm_cogni import CogniSwarmAgent


def format_as_json(analysis_data: str) -> str:
    """
    Formats the provided analysis data string into a JSON string.
    Expects the input string to contain the core reflection, exploration points, and analysis.
    It will structure this into a predefined JSON format.
    Args:
        analysis_data: A string containing the reflection, exploration, and analysis insights.
    Returns:
        A JSON string representing the structured analysis, or an error message if formatting fails.
    """
    try:
        # Basic parsing attempt (assuming structure might be loose)
        # A more robust implementation might use regex or LLM prompting within the tool
        # to extract specific fields if the input `analysis_data` format is unpredictable.
        # For now, we'll wrap the whole input under an "analysis" key.
        output_dict = {
            "analysis_summary": analysis_data,
            # Potential future fields:
            # "reflection": extracted_reflection,
            # "exploration_topics": extracted_topics,
            # "analyzer_feedback": extracted_feedback
        }
        # Return only the JSON string
        return json.dumps(output_dict, indent=2)
    except Exception as e:
        # Return only the error JSON
        return json.dumps({"error": f"Failed to format analysis into JSON: {e}"})


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
    content = (
        f"tags:: #thought\n\n# Thought {timestamp}\n\n{ai_content}\n\nTime: {now.isoformat()}\n"
    )

    # Save to file
    filepath = os.path.join(THOUGHTS_DIR, f"{timestamp}.md")
    os.makedirs(THOUGHTS_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    return timestamp, filepath


@task
def create_initial_thought(
    memory_adapter: CogniLangchainMemoryAdapter, custom_prompt: str = None
) -> Dict[str, Any]:
    """
    Creates the initial thought using CoreCogniAgent and saves context to shared memory.

    Args:
        memory_adapter: The memory adapter to use
        custom_prompt: Optional custom prompt to use instead of the default
    """
    logger = get_run_logger()

    try:
        logger.info("Creating initial thought...")

        # Instantiate agent, passing the flow's shared memory bank
        core_cogni = CoreCogniAgent(
            agent_root=Path(THOUGHTS_DIR),
            memory=memory_adapter.memory_bank,
            project_root_override=Path(BASE_DIR),
        )

        # Pass custom_prompt to prepare_input if provided
        prepared_input = core_cogni.prepare_input(prompt=custom_prompt)
        initial_prompt = prepared_input.get(
            "prompt",
            "Hi Cogni, there was no prepared prompt. Please generate any thought you want.",
        )

        logger.info(f"Prompt: {initial_prompt}")

        result_data = core_cogni.act(prepared_input)
        initial_thought = result_data.get("thought_content", "[No thought content]")
        memory_adapter.save_context(
            inputs={"input": initial_prompt}, outputs={"output": initial_thought}
        )
        logger.info("Saved initial thought context to history via adapter.")

        try:
            core_cogni.record_action(result_data, prefix="thought_")
            logger.info("Logged detailed initial thought action via record_action.")
        except Exception as e:
            logger.warning(f"Could not log detailed action for initial thought: {e}")

        logger.info(f"INITIAL THOUGHT OUTPUT: {initial_thought}")
        return result_data

    except Exception as e:
        logger.error(f"Error in initial thought generation: {e}", exc_info=True)
        return {"error": str(e), "thought_content": "[Error generating thought]"}


@task
async def process_with_swarm(
    initial_thought_content: str, memory_adapter: CogniLangchainMemoryAdapter
) -> Dict[str, Any]:
    """
    Process the initial thought using the CogniSwarmAgent.
    """
    logger = get_run_logger()

    if (
        not initial_thought_content
        or "[Error generating thought]" in initial_thought_content
        or "[No thought content]" in initial_thought_content
    ):
        logger.warning(
            "Skipping swarm processing due to missing or invalid initial thought content."
        )
        return {"output": "[Skipped Swarm Processing]", "raw_result": []}

    try:
        logger.info(f"Processing thought with SwarmCogni: '{initial_thought_content[:100]}...'")

        # Load OpenAI API key from Prefect Secret
        try:
            logger.info("Loading OpenAI API key from Prefect Secret block 'openai-api-key'...")
            openai_api_key_block = await Secret.load("openai-api-key")
            openai_api_key = openai_api_key_block.get()
            logger.info("Successfully loaded OpenAI API key from Prefect Secret block.")
        except ValueError as e:
            logger.error(f"Failed to load Prefect Secret 'openai-api-key': {e}.")
            raise ValueError(
                "Failed to load required 'openai-api-key' Prefect Secret block."
            ) from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading the Prefect secret: {e}")
            raise

        # Initialize the CogniSwarmAgent
        swarm_cogni = CogniSwarmAgent(
            agent_root=Path(THOUGHTS_DIR),
            memory=memory_adapter.memory_bank,
            project_root_override=Path(BASE_DIR),
            openai_api_key=openai_api_key,
        )

        # Process the thought
        prepared_input = swarm_cogni.prepare_input(thought=initial_thought_content)
        result_data = await swarm_cogni.a_act(prepared_input)

        return result_data

    except Exception as e:
        logger.error(f"Error in swarm processing: {e}", exc_info=True)
        return {"error": str(e), "output": "[Error during swarm processing]", "raw_result": []}


@flow
def ritual_of_presence_flow(custom_prompt: Optional[str] = None):
    """
    Flow generating an initial thought and using a swarm for reflection.

    Args:
        custom_prompt: Optional custom prompt to use instead of the default
    """
    logger = get_run_logger()
    logger.info("Starting Ritual of Presence flow (Core Cogni + SwarmCogni)...")

    # --- Initialize Shared Memory ---
    flow_project_name = "ritual_of_presence"
    flow_session_id = "ritual-session"  # Keep fixed session ID for persistence

    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)

    flow_memory_bank = FileMemoryBank(
        memory_bank_root=memory_root,
        project_name=f"flows/{flow_project_name}",
        session_id=flow_session_id,
    )
    shared_memory_adapter = CogniLangchainMemoryAdapter(memory_bank=flow_memory_bank)

    session_id = flow_memory_bank.session_id
    session_path = flow_memory_bank._get_session_path()
    logger.info(
        f"Initialized shared memory for project 'flows/{flow_project_name}', session '{session_id}' at {session_path}"
    )

    # --- Run Agent Tasks Sequentially ---
    # 1. Create initial thought with CoreCogniAgent
    initial_result = create_initial_thought(
        memory_adapter=shared_memory_adapter, custom_prompt=custom_prompt
    )

    if "error" in initial_result:
        logger.error("Flow aborted due to error in initial thought generation.")
        return f"Flow failed during initial thought: {initial_result['error']}"

    # Extract the thought content to pass to the swarm
    initial_thought_content = initial_result.get("thought_content", "[Missing thought content]")

    # 2. Process with SwarmCogni
    swarm_result_future = process_with_swarm.submit(
        initial_thought_content=initial_thought_content, memory_adapter=shared_memory_adapter
    )
    # Wait for the future to complete and get the result
    swarm_result = swarm_result_future.result()

    # Check result
    if isinstance(swarm_result, dict) and "error" in swarm_result:
        logger.error("Flow completed with error in swarm processing.")
        error_msg = str(swarm_result.get("error", "Unknown swarm error"))
        return f"Flow completed with error during swarm processing: {error_msg}"
    elif isinstance(swarm_result, Exception):
        logger.error(f"Flow failed during swarm processing task: {swarm_result}")
        return f"Flow failed: {swarm_result}"

    logger.info("Ritual of Presence flow (Core + SwarmCogni) completed successfully.")
    return f"Ritual of Presence completed. Session: {session_id}. See logs and memory bank: {session_path}"


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the Ritual of Presence flow")
    parser.add_argument(
        "-custom_prompt",
        "--custom_prompt",
        type=str,
        help="Custom prompt to use instead of the default",
    )
    args = parser.parse_args()

    print("Running Ritual of Presence (Core + SwarmCogni)...")

    # Run the flow with custom prompt if provided
    result_message = ritual_of_presence_flow(custom_prompt=args.custom_prompt)
    print(result_message)
