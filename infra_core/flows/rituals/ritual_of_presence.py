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
import json # Added for JSON tool
from prefect.blocks.system import Secret # Added for Prefect Secret

# --- Project Constants Import ---
from infra_core.constants import MEMORY_BANKS_ROOT, THOUGHTS_DIR, BASE_DIR

# --- Memory Imports ---
from infra_core.memory.memory_bank import CogniMemoryBank, CogniLangchainMemoryAdapter

# --- Agent Imports ---
from infra_core.cogni_agents.core_cogni import CoreCogniAgent

# --- AutoGen Imports (Standard Pattern) ---
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

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
        
        # Instantiate agent, passing the flow's shared memory bank
        core_cogni = CoreCogniAgent(
            agent_root=Path(THOUGHTS_DIR), # <--- Corrected to pass Path(THOUGHTS_DIR) directly
            memory=memory_adapter.memory_bank, # Pass the flow's bank instance
            project_root_override=Path(BASE_DIR) # Pass project root for context loading
        )
        
        prepared_input = core_cogni.prepare_input()
        initial_prompt = prepared_input.get("prompt", "Generate initial thought.")
        result_data = core_cogni.act(prepared_input)
        initial_thought = result_data.get("thought_content", "[No thought content]")
        memory_adapter.save_context(inputs={"input": initial_prompt}, outputs={"output": initial_thought})
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
        return {"error": str(e), "thought_content": "[Error generating thought]"} # Ensure key exists

@task
async def run_reflection_groupchat(initial_thought_content: str, memory_adapter: CogniLangchainMemoryAdapter) -> Dict[str, Any]:
    """
    Asynchronously runs an AutoGen GroupChat to reflect, explore, analyze, and output JSON.
    """
    logger = get_run_logger()

    if not initial_thought_content or "[Error generating thought]" in initial_thought_content or "[No thought content]" in initial_thought_content:
        logger.warning("Skipping reflection groupchat due to missing or invalid initial thought content.")
        return {"final_response": "[Skipped GroupChat]", "messages": []}

    try:
        logger.info(f"Starting reflection groupchat for thought: '{initial_thought_content[:100]}...'")

        # --- Define LLM Config (using Prefect Secret) ---
        logger.info("Preparing LLM configuration using Prefect Secret...")
        
        # 1. Define desired models
        # We still need a basic config_list structure for AutoGen agents
        desired_models = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        config_list = [{"model": model_name} for model_name in desired_models]
        logger.info(f"Base config_list created for models: {desired_models}")

        # 2. Load API Key from Prefect Secret Block
        try:
            logger.info("Loading OpenAI API key from Prefect Secret block 'openai-api-key'...")
            openai_api_key_block = await Secret.load("openai-api-key") # Added await
            openai_api_key = openai_api_key_block.get()
            logger.info("Successfully loaded OpenAI API key from Prefect Secret block.")

            # 3. Inject the loaded API key into the config_list for OpenAI models
            for config in config_list:
                # Check if it's an OpenAI model config (adjust this check if needed)
                if isinstance(config, dict) and config.get("model", "").startswith("gpt"):
                    config["api_key"] = openai_api_key
                    logger.debug(f"Injected Prefect secret into config for model: {config.get('model')}")

        except ValueError as e:
            logger.error(f"Failed to load Prefect Secret 'openai-api-key': {e}. Ensure the block exists and is accessible.", exc_info=True)
            raise ValueError("Failed to load required 'openai-api-key' Prefect Secret block.") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred while loading or injecting the Prefect secret: {e}", exc_info=True)
            raise # Reraise the original exception

        # --- LLM Config Definitions ---
        # Base config for Manager and non-tool agents
        base_llm_config = {
            "config_list": config_list,
            "cache_seed": 42, 
            "timeout": 120,
        }

        # Specific config for the agent that needs to call the tool
        tool_agent_llm_config = base_llm_config.copy() # Start with base config
        tool_agent_llm_config["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "format_as_json",
                    "description": "Formats the provided analysis data string into a JSON string.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "analysis_data": {
                                "type": "string",
                                "description": "A string containing the reflection, exploration, and analysis insights."
                            }
                        },
                        "required": ["analysis_data"],
                    },
                }
            }
        ]

        logger.info(f"Loaded LLM Config for models: {[cfg.get('model') for cfg in config_list]}")
        
        try:
            # --- Define Agents ---
            reflector = AssistantAgent(
                name="Reflector",
                system_message="You are the Reflector. Reflect deeply on the input thought: Extract meaning, assumptions, implications. Provide a concise reflection, 1 brief sentence.",
                llm_config=base_llm_config, # Use base config
            )
            explorer = AssistantAgent(
                name="Explorer",
                system_message="You are the Explorer. Based *only* on the Reflector's output, list exactly 1 distinct topic/question for further exploration.",
                llm_config=base_llm_config, # Use base config
            )
            analyzer = AssistantAgent(
                name="Analyzer",
                system_message="You are the Analyzer. Review the Reflector's reflection and Explorer's points. Provide a brief, synthesized analysis text. **This text will be passed to the JSON_Outputter.**",
                llm_config=base_llm_config, # Use base config
            )
            
            # Define JSON_Outputter with updated prompt directly
            json_outputter = AssistantAgent(
                name="JSON_Outputter",
                llm_config=tool_agent_llm_config, # Use config with tool schema
                system_message="First, call the function 'format_as_json' with the analysis text provided by the Analyzer as the 'analysis_data' argument. " \
                              "Then, on the very next line, output the single word TERMINATE."
            )

            # User Proxy Agent - acts as initiator and executor
            user_proxy = UserProxyAgent(
                name="ExecutorAgent", # Keep name for clarity
                human_input_mode="NEVER",
                max_consecutive_auto_reply=4, # Reset to lower value
                is_termination_msg=lambda x: x.get("content", "").strip().endswith("TERMINATE"), # Standard check
                code_execution_config=False, # Keep False
                # Revert system message - just execute functions
                system_message="A proxy agent that executes function calls when requested."
                # Remove llm_config - not needed for basic execution
            )

            # Register the function with the User Proxy Agent
            user_proxy.register_function(function_map={"format_as_json": format_as_json})

            # --- Create Group Chat & Manager ---
            groupchat = GroupChat(
                agents=[user_proxy, reflector, explorer, analyzer, json_outputter],
                messages=[],
                max_round=15, 
                speaker_selection_method="auto" 
            )
            manager = GroupChatManager(groupchat=groupchat, llm_config=base_llm_config)

            # --- Run Group Chat ---
            task_prompt = f"Initial Thought to process:\n\n{initial_thought_content}"
            logger.info("Initiating group chat...")

            # Initiate chat FROM UserProxy TO the Manager
            chat_result = await user_proxy.a_initiate_chat(
                manager, 
                message=task_prompt,
            )

            # --- Process Results ---
            final_output = "[No function execution result found]"
            all_messages = chat_result.chat_history if chat_result and chat_result.chat_history else []
            
            # Extract the last message or summary
            # Prioritize extracting the content from the specific function call result
            function_result_found = False
            if chat_result and chat_result.chat_history:
                for msg in reversed(chat_result.chat_history): # Check recent messages first
                    # Check for role 'tool' or 'function' for robustness
                    if (msg.get("role") == "tool" or msg.get("role") == "function") and msg.get("name") == "format_as_json":
                        final_output = msg.get("content", final_output)
                        logger.info("Extracted final output from format_as_json function result.")
                        function_result_found = True
                        break # Found the result, stop searching
                # Fallback logic ONLY if the function result wasn't found in the history
                if not function_result_found:
                    if chat_result.summary: # Fallback to summary
                        final_output = chat_result.summary
                        logger.info("Using chat summary as final output.")
            
            logger.info(f"GROUP CHAT FINAL OUTPUT/SUMMARY: {final_output}")
            
            result_data = {
                "final_response": final_output,
                "messages": all_messages
            }

            # --- Save Context (Simplified) ---
            try:
                memory_adapter.save_context(inputs={"input": task_prompt}, outputs={"output": final_output})
                logger.info("Saved group chat input/output context to history.")
            except Exception as e:
                logger.warning(f"Could not save group chat context to memory adapter: {e}")

            return result_data

        except Exception as e:
            logger.error(f"Error during reflection groupchat execution: {e}", exc_info=True)
            return {"error": str(e), "final_response": "[Error during groupchat execution]", "messages": []}

    except Exception as e:
        logger.error(f"Error in reflection groupchat execution: {e}", exc_info=True)
        return {"error": str(e), "final_response": "[Error during groupchat execution]", "messages": []}

@flow
def ritual_of_presence_flow():
    """Flow generating an initial thought and using a swarm for reflection."""
    logger = get_run_logger()
    logger.info("Starting Ritual of Presence flow (Core Cogni + Reflection GroupChat)...")

    # --- Initialize Shared Memory ---
    flow_project_name = "ritual_of_presence"
    flow_session_id = "ritual-session" # Keep fixed session ID for persistence
    
    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)
    
    flow_memory_bank = CogniMemoryBank(
        memory_bank_root=memory_root, 
        project_name=f"flows/{flow_project_name}", 
        session_id=flow_session_id
    )
    shared_memory_adapter = CogniLangchainMemoryAdapter(memory_bank=flow_memory_bank)
    
    session_id = flow_memory_bank.session_id 
    session_path = flow_memory_bank._get_session_path() 
    logger.info(f"Initialized shared memory for project 'flows/{flow_project_name}', session '{session_id}' at {session_path}")

    # --- Run Agent Tasks Sequentially ---
    initial_result = create_initial_thought(memory_adapter=shared_memory_adapter)
    
    if "error" in initial_result:
        logger.error("Flow aborted due to error in initial thought generation.")
        return f"Flow failed during initial thought: {initial_result['error']}"

    # Extract the thought content to pass to the swarm
    initial_thought_content = initial_result.get("thought_content", "[Missing thought content]")

    # Run the async swarm task (Prefect handles scheduling async tasks)
    groupchat_result_future = run_reflection_groupchat.submit(
        initial_thought_content=initial_thought_content, 
        memory_adapter=shared_memory_adapter
    )
    # Wait for the future to complete and get the result
    groupchat_result = groupchat_result_future.result()

    # Check result after await resolves if run_reflection_groupchat was waited on, 
    # or handle the future if not awaited directly in flow context.
    # Since Prefect runs it, we check the result object directly.
    if isinstance(groupchat_result, dict) and "error" in groupchat_result:
        logger.error("Flow completed with error in reflection groupchat execution.")
        # Ensure groupchat_result['error'] exists and is stringifiable
        error_msg = str(groupchat_result.get('error', 'Unknown groupchat error'))
        return f"Flow completed with error during reflection groupchat: {error_msg}"
    elif isinstance(groupchat_result, Exception): # Handle case where task submission itself failed
        logger.error(f"Flow failed during reflection groupchat task submission/execution: {groupchat_result}")
        return f"Flow failed: {groupchat_result}"
    
    logger.info("Ritual of Presence flow (Core + GroupChat) completed successfully.")
    return f"Ritual of Presence (GroupChat) completed. Session: {session_id}. See logs and memory bank: {session_path}"

if __name__ == "__main__":
    # Ensure necessary environment variables (like OPENAI_API_KEY) are set
    # or llm_config.json is present
    print("Running Ritual of Presence (Core + GroupChat)...")
    
    # Prefect flows can be run directly
    # If run as a script, the flow decorator handles execution.
    # No need for explicit asyncio.run typically.
    result_message = ritual_of_presence_flow()
    print(result_message)
