"""
CogniDAO Presence Agent Nodes.

Agent logic and node functions for the CogniDAO presence graph with MCP reconnection support.
"""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import SystemMessage
from src.shared_utils import (
    CogniAgentState,
    get_cached_bound_model,
    get_logger,
)
from src.shared_utils.prompt_templates import PromptTemplateManager
from src.shared_utils.tool_registry import get_tools

logger = get_logger(__name__)


def create_agent_node() -> Callable[[CogniAgentState, dict[str, Any]], dict[str, Any]]:
    """Create the main agent node function."""

    async def agent_node(state: CogniAgentState, config: dict[str, Any]) -> dict[str, Any]:
        """
        Call the model with MCP tools and system prompt.

        Args:
            state: Current agent state
            config: Configuration dictionary

        Returns:
            Updated state with model response
        """
        # Get tools (MCP client handles all connection logic internally)
        tools = await get_tools("cogni")

        # Generate system prompt using template
        template_manager = PromptTemplateManager()
        tool_specs = template_manager.generate_tool_specs_from_mcp_tools(tools)
        system_prompt = template_manager.render_agent_prompt(
            "cogni_presence", 
            tool_specs=tool_specs,
            task_context=""
        )
        
        # Prepare messages with templated system prompt
        messages = state["messages"]
        messages_with_system = [SystemMessage(content=system_prompt)] + list(messages)

        # Get cached bound model and invoke
        model_name = config.get("configurable", {}).get("model_name") or "gpt-4o-mini"
        model = get_cached_bound_model(model_name, tools)
        response = await model.ainvoke(messages_with_system)

        return {"messages": [response]}

    return agent_node


def should_continue(state: CogniAgentState) -> str:
    """
    Determine whether to continue or end based on the last message.

    Args:
        state: Current agent state

    Returns:
        "continue" to call tools, "end" to finish
    """
    messages = state["messages"]
    last_message = messages[-1]

    # If the last message has tool calls, continue
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"

    return "end"
