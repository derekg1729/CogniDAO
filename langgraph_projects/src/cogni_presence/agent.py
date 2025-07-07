"""
CogniDAO Presence Agent Nodes.

Agent logic and node functions for the CogniDAO presence graph.
"""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import SystemMessage
from src.shared_utils import (
    COGNI_SYSTEM_PROMPT,
    CogniAgentState,
    get_cached_bound_model,
    get_logger,
    get_mcp_tools,
    log_model_binding,
)

logger = get_logger(__name__)


def create_agent_node() -> Callable[[CogniAgentState, dict[str, Any]], dict[str, Any]]:
    """
    Create the main agent node function.

    Returns:
        Agent node function
    """

    async def agent_node(state: CogniAgentState, config: dict[str, Any]) -> dict[str, Any]:
        """
        Call the model with MCP tools and system prompt.

        Args:
            state: Current agent state
            config: Configuration dictionary

        Returns:
            Updated state with model response
        """
        # Get MCP tools
        tools = await get_mcp_tools(server_type="cogni")

        # Prepare messages with system prompt
        messages = state["messages"]
        messages_with_system = [SystemMessage(content=COGNI_SYSTEM_PROMPT)] + list(messages)

        # Handle case where model_name is explicitly None (not just missing)
        model_name = config.get("configurable", {}).get("model_name") or "gpt-4o-mini"

        # Get cached bound model
        model = get_cached_bound_model(model_name, tools)

        # Log model binding
        log_model_binding(model_name, len(tools))

        # Invoke the model
        response = await model.ainvoke(messages_with_system)

        return {"messages": [response]}

    return agent_node


def should_continue(state: CogniAgentState) -> str:
    """
    Determine whether to continue to tool execution or end the conversation.

    Args:
        state: Current agent state

    Returns:
        Either "continue" or "end"
    """
    messages = state["messages"]

    # Guard against empty messages
    if not messages:
        return "end"

    last_message = messages[-1]

    # Check if the last message has tool calls
    tool_calls = getattr(last_message, "tool_calls", None)
    if tool_calls:
        return "continue"
    else:
        return "end"
