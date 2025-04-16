import asyncio
from typing import Dict, Any, Optional

from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from infra_core.tools.format_as_json_tool import format_as_json_tool, format_as_json

class CogniSwarmAgent:
    def __init__(
        self,
        name: str = "SwarmCogni",
        spirit_path = None,
        agent_root = None,
        memory = None,
        project_root_override = None,
        openai_api_key: Optional[str] = None
    ):
        self.name = name
        self.agent_root = agent_root
        self.memory = memory
        self.project_root_override = project_root_override
        self.openai_api_key = openai_api_key
        self.swarm = self._build_swarm()

    def _build_swarm(self):
        config_list = [{"model": "gpt-4o", "api_key": self.openai_api_key}]
        base_llm_config = {"config_list": config_list, "cache_seed": 42, "timeout": 120}
        
        # Configure the LLM to use the function tool
        # Use the function directly imported from the module
        function_map = {format_as_json_tool.name: format_as_json}  # Use imported function
        tool_agent_llm_config = {
            "config_list": config_list,
            "cache_seed": 42,
            "timeout": 120,
            "functions": [format_as_json_tool.schema]
        }

        reflector = AssistantAgent(
            name="Reflector",
            system_message="Reflect on the thought and provide a brief summary.",
            llm_config=base_llm_config
        )

        analyzer = AssistantAgent(
            name="JSON_Outputter",
            system_message="After receiving a reflection, summarize it and then say TERMINATE.",
            llm_config=tool_agent_llm_config
        )

        user_proxy = UserProxyAgent(
            name="Executor",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
            code_execution_config=False,
            is_termination_msg=lambda msg: msg.get("content", "").strip().endswith("TERMINATE"),
            system_message="Execute functions when requested.",
            function_map=function_map  # Register the function directly in the constructor
        )

        groupchat = GroupChat(agents=[user_proxy, reflector, analyzer], messages=[], max_round=10)
        manager = GroupChatManager(groupchat=groupchat, llm_config=base_llm_config)

        return {"user_proxy": user_proxy, "manager": manager}

    def prepare_input(self, thought: Optional[str] = None) -> Dict[str, Any]:
        """Prepare input for the agent."""
        if thought:
            return {"thought": thought}
        return {"thought": "Reflect on a meaningful thought."}

    def record_action(self, output: Dict[str, Any], prefix: str = "") -> None:
        """Record action to memory if memory is available."""
        if self.memory and hasattr(self.memory, 'log_decision'):
            try:
                self.memory.log_decision({
                    "agent_name": self.name, 
                    "action_type": prefix, 
                    "output": output
                })
            except Exception as e:
                print(f"Error logging decision: {e}")

    async def a_act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return results in the expected format."""
        thought = prepared_input.get("thought", "")
        chat_result = await self.swarm["user_proxy"].a_initiate_chat(
            self.swarm["manager"], 
            message=thought
        )
        
        # Extract the final output
        final_output = ""
        all_messages = chat_result.chat_history if hasattr(chat_result, 'chat_history') else []
        
        # Look for function call result
        for msg in reversed(all_messages):
            if msg.get("role") == "tool" and msg.get("name") == format_as_json_tool.name:
                final_output = msg.get("content", "")
                break
        
        result = {
            "output": final_output,
            "raw_result": all_messages,
            "thought_content": thought
        }
        
        return result

    def act(self, thought: str) -> Dict[str, Any]:
        return asyncio.run(self.a_act(self.prepare_input(thought)))
