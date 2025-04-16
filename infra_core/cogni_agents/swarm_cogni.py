import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
from infra_core.tools.format_as_json_tool import format_as_json_tool, format_as_json
from infra_core.tools.broadcast_queue_tool import add_to_broadcast_queue_tool, add_to_broadcast_queue
from infra_core.cogni_agents.base import CogniAgent

class CogniSwarmAgent(CogniAgent):
    def __init__(
        self,
        name: str = "SwarmCogni",
        spirit_path = None,
        agent_root = None,
        memory = None,
        project_root_override = None,
        openai_api_key: Optional[str] = None
    ):
        # Call parent constructor with the required parameters
        super().__init__(
            name=name, 
            spirit_path=spirit_path or Path("infra_core/cogni_spirit/spirits/swarm-cogni.md"), 
            agent_root=agent_root, 
            memory=memory, 
            project_root_override=project_root_override
        )
        self.openai_api_key = openai_api_key
        self.swarm = self._build_swarm()

    def _build_swarm(self):
        config_list = [{"model": "gpt-4o", "api_key": self.openai_api_key}]
        base_llm_config = {"config_list": config_list, "cache_seed": 42, "timeout": 120}
        
        # Configure the LLM to use the function tools
        # Use the functions directly imported from the modules
        function_map = {
            format_as_json_tool.name: format_as_json,
            add_to_broadcast_queue_tool.name: add_to_broadcast_queue
        }
        
        tool_agent_llm_config = {
            "config_list": config_list,
            "cache_seed": 42,
            "timeout": 120,
            "functions": [
                format_as_json_tool.schema,
                add_to_broadcast_queue_tool.schema
            ]
        }

        reflector = AssistantAgent(
            name="Reflector",
            system_message="Reflect on the thought, and how to effectively communicate it via a tweet. Then respond with ONLY the contents of the tweet.",
            llm_config=base_llm_config
        )

        # analyzer = AssistantAgent(
        #     name="JSON_Outputter",
        #     system_message="After receiving a reflection, summarize it and then say TERMINATE.",
        #     llm_config=tool_agent_llm_config
        # )

        curator = AssistantAgent(
            name="Curator",
            system_message=(
                "You are the Content Curator.\n"
                "\n"
                "Your job is to review the given reflection and decide if it is suitable for broadcast.\n"
                "\n"
                "### RULES:\n"
                "- If the reflection is **clear, empowering, and aligned with the mission**, you MUST call the add_to_broadcast_queue function with:\n"
                "    * content - The reflection text to broadcast\n" 
                "    * source - Set to 'reflection'\n"
                "    * priority - A number from 1-5 (1 highest, 5 lowest) based on importance\n"
                "    * Example function call format: add_to_broadcast_queue(content=\"The reflection text\", source=\"reflection\", priority=2)\n"
                "    * After calling the function, say TERMINATE\n"
                "- If the reflection is **not** suitable:\n"
                "    - Suggest an improvement in natural language\n"
                "    - Do NOT call any functions\n"
                "\n"
                "Important: You MUST use the exact function name and parameter names as shown in the example.\n"
            ),
            llm_config=tool_agent_llm_config
        )


        user_proxy = UserProxyAgent(
            name="Executor",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=3,
            code_execution_config=False,
            is_termination_msg=lambda msg: msg.get("content", "").strip().endswith("TERMINATE"),
            system_message="Execute functions when requested.",
            function_map=function_map  # Register the functions in the map
        )

        groupchat = GroupChat(agents=[user_proxy, reflector, curator], messages=[], max_round=10)
        manager = GroupChatManager(groupchat=groupchat, llm_config=base_llm_config)

        return {"user_proxy": user_proxy, "manager": manager}

    def prepare_input(self, thought: Optional[str] = None) -> Dict[str, Any]:
        """Prepare input for the agent."""
        if thought:
            return {"thought": thought}
        return {"thought": "Reflect on a meaningful thought."}

    # def record_action(self, output: Dict[str, Any], prefix: str = "") -> None:
    #     """Record action to memory if memory is available."""
    #     if self.memory and hasattr(self.memory, 'log_decision'):
    #         try:
    #             self.memory.log_decision({
    #                 "agent_name": self.name, 
    #                 "action_type": prefix, 
    #                 "output": output
    #             })
    #         except Exception as e:
    #             print(f"Error logging decision: {e}")

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
        
        # Record the result to memory before returning
        self.record_action(result, prefix="swarm_reflection")
        
        return result

    def act(self, thought: str) -> Dict[str, Any]:
        return asyncio.run(self.a_act(self.prepare_input(thought)))
