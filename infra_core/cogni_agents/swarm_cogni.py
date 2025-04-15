import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import json

# Import base CogniAgent class
from infra_core.cogni_agents.base import CogniAgent

# Import memory components
from infra_core.memory.memory_bank import BaseCogniMemory

# AutoGen imports
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

class CogniSwarmAgent(CogniAgent):
    """
    A concrete implementation of CogniAgent that wraps and runs an AutoGen swarm.
    Implements reflection, exploration, analysis, and JSON formatting through multi-agent system.
    """
    
    def __init__(
        self,
        name: str = "SwarmCogni",
        spirit_path: Path = Path("infra_core/cogni_spirit/spirits/swarm-cogni.md"),
        agent_root: Path = None,
        memory: BaseCogniMemory = None,
        project_root_override: Optional[Path] = None,
        openai_api_key: Optional[str] = None
    ):
        """
        Initialize the CogniSwarmAgent with a swarm of AutoGen agents.
        
        Args:
            name (str): The name of the agent
            spirit_path (Path): Path to the agent's spirit guide
            agent_root (Path): Root directory for agent outputs
            memory (BaseCogniMemory): Memory bank for the agent
            project_root_override (Optional[Path]): Optional override for project root
            openai_api_key (Optional[str]): OpenAI API key for AutoGen agents
        """
        super().__init__(
            name=name,
            spirit_path=spirit_path,
            agent_root=agent_root,
            memory=memory,
            project_root_override=project_root_override
        )
        
        self.openai_api_key = openai_api_key
        self.swarm = self._build_swarm()
        
    def _format_as_json(self, analysis_data: str) -> str:
        """
        Formats the provided analysis data string into a JSON string.
        
        Args:
            analysis_data: A string containing the reflection, exploration, and analysis insights.
        Returns:
            A JSON string representing the structured analysis.
        """
        try:
            output_dict = {
                "analysis_summary": analysis_data,
            }
            return json.dumps(output_dict, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to format analysis into JSON: {e}"})
            
    def _build_swarm(self):
        """
        Build the AutoGen swarm with reflector, explorer, analyzer, and JSON outputter agents.
        
        Returns:
            A structure containing the user proxy and manager agents.
        """
        # Define desired models and create config list
        desired_models = ["gpt-4o", "gpt-4", "gpt-3.5-turbo"]
        config_list = [{"model": model_name} for model_name in desired_models]
        
        # Inject API key if provided
        if self.openai_api_key:
            for config in config_list:
                if isinstance(config, dict) and config.get("model", "").startswith("gpt"):
                    config["api_key"] = self.openai_api_key
        
        # Base config for Manager and non-tool agents
        base_llm_config = {
            "config_list": config_list,
            "cache_seed": 42, 
            "timeout": 120,
        }

        # Specific config for the agent that needs to call the tool
        tool_agent_llm_config = base_llm_config.copy()
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
        
        # Create agents
        reflector = AssistantAgent(
            name="Reflector",
            system_message="You are the Reflector. Reflect deeply on the input thought: Extract meaning, assumptions, implications. Provide a concise reflection, 1 brief sentence.",
            llm_config=base_llm_config,
        )
        
        explorer = AssistantAgent(
            name="Explorer",
            system_message="You are the Explorer. Based *only* on the Reflector's output, list exactly 1 distinct topic/question for further exploration.",
            llm_config=base_llm_config,
        )
        
        analyzer = AssistantAgent(
            name="Analyzer",
            system_message="You are the Analyzer. Review the Reflector's reflection and Explorer's points. Provide a brief, synthesized analysis text. **This text will be passed to the JSON_Outputter.**",
            llm_config=base_llm_config,
        )
        
        json_outputter = AssistantAgent(
            name="JSON_Outputter",
            llm_config=tool_agent_llm_config,
            system_message="First, call the function 'format_as_json' with the analysis text provided by the Analyzer as the 'analysis_data' argument. " \
                          "Then, on the very next line, output the single word TERMINATE."
        )
        
        # User Proxy Agent
        user_proxy = UserProxyAgent(
            name="ExecutorAgent",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=4,
            is_termination_msg=lambda x: x.get("content", "").strip().endswith("TERMINATE"),
            code_execution_config=False,
            system_message="A proxy agent that executes function calls when requested."
        )
        
        # Register the function with the User Proxy Agent
        user_proxy.register_function(function_map={"format_as_json": self._format_as_json})
        
        # Create Group Chat & Manager
        groupchat = GroupChat(
            agents=[user_proxy, reflector, explorer, analyzer, json_outputter],
            messages=[],
            max_round=15, 
            speaker_selection_method="auto" 
        )
        
        manager = GroupChatManager(groupchat=groupchat, llm_config=base_llm_config)
        
        # Return a structure with both the user_proxy and manager
        return {
            "user_proxy": user_proxy,
            "manager": manager
        }
    
    def prepare_input(self, thought: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare input for the agent.
        
        Args:
            thought (Optional[str]): Optional thought content to reflect on
            
        Returns:
            Dict[str, Any]: Prepared input dictionary
        """
        if thought:
            return {"thought": thought}
        return {"thought": "Reflect on a meaningful thought."}
    
    async def a_act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Asynchronously run the swarm to process the input thought.
        
        Args:
            prepared_input (Dict[str, Any]): Prepared input with a "thought" key
            
        Returns:
            Dict[str, Any]: Result of the swarm processing
        """
        message = prepared_input.get("thought", "Reflect on this idea.")
        
        # Initiate chat
        chat_result = await self.swarm["user_proxy"].a_initiate_chat(
            self.swarm["manager"], 
            message=message,
        )
        
        # Extract the final output
        final_output = "[No function execution result found]"
        all_messages = chat_result.chat_history if chat_result and chat_result.chat_history else []
        
        # Look for function call result
        function_result_found = False
        if chat_result and chat_result.chat_history:
            for msg in reversed(chat_result.chat_history):
                if (msg.get("role") == "tool" or msg.get("role") == "function") and msg.get("name") == "format_as_json":
                    final_output = msg.get("content", final_output)
                    function_result_found = True
                    break
                    
            # Fallback to summary if function result not found
            if not function_result_found and chat_result.summary:
                final_output = chat_result.summary
        
        return {
            "output": final_output,
            "raw_result": all_messages,
            "thought_content": message
        }
        
    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronously run the swarm to process the input thought.
        
        Args:
            prepared_input (Dict[str, Any]): Prepared input with a "thought" key
            
        Returns:
            Dict[str, Any]: Result of the swarm processing
        """
        return asyncio.run(self.a_act(prepared_input)) 