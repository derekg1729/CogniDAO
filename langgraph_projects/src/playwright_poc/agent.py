"""
Playwright Agent Nodes.

Agent logic and node functions for the Playwright browser automation graph with MCP reconnection support.
"""

from collections.abc import Callable
from typing import Any

from langchain_core.messages import SystemMessage, AIMessage
from src.shared_utils import (
    PlaywrightAgentState,
    get_cached_bound_model,
    get_logger,
    get_mcp_tools_with_refresh,
    get_mcp_connection_info,
    log_model_binding,
)
from src.shared_utils.prompt_templates import (
    render_playwright_navigator_prompt,
    PromptTemplateManager,
)

logger = get_logger(__name__)

# Template manager for generating dynamic prompts
template_manager = PromptTemplateManager()

# Global variable for runtime tools - initialized once per process
_runtime_tools = None

async def get_runtime_tools(server_type: str):
    """Get MCP tools with lazy initialization - connect once per process."""
    global _runtime_tools
    if _runtime_tools is None:
        _runtime_tools = await get_mcp_tools_with_refresh(server_type=server_type)
    return _runtime_tools


def create_agent_node() -> Callable[[PlaywrightAgentState, dict[str, Any]], dict[str, Any]]:
    """
    Create the main agent node function with MCP reconnection support.

    Returns:
        Agent node function
    """

    async def agent_node(state: PlaywrightAgentState, config: dict[str, Any]) -> dict[str, Any]:
        """
        Call the model with Playwright MCP tools and system prompt, with automatic MCP reconnection.

        Args:
            state: Current agent state
            config: Configuration dictionary

        Returns:
            Updated state with model response
        """
        try:
            # Get MCP tools with lazy initialization (connects once per process)
            tools = await get_runtime_tools(server_type="playwright")

            # Get connection info for logging
            connection_info = get_mcp_connection_info(server_type="playwright")

            # Debug: Log complete connection info
            logger.debug(f"🔍 Complete connection info: {connection_info}")

            # Log connection status
            if connection_info["state"] == "failed":
                logger.warning(
                    f"🔄 MCP connection failed (state: {connection_info['state']}, "
                    f"retry: {connection_info['retry_count']}/{connection_info['max_retries']})"
                )
            else:
                logger.info(
                    f"✅ Using {connection_info['tools_count']} MCP tools (state: {connection_info['state']})"
                )

            # Generate tool specs for the template
            tool_specs = template_manager.generate_tool_specs_from_mcp_tools(tools)
            
            # Get configuration for target URL and task context
            target_url = config.get("configurable", {}).get("target_url", "http://host.docker.internal:3000")
            task_context = config.get("configurable", {}).get("task_context", "")
            
            # Generate system prompt using template
            system_prompt = render_playwright_navigator_prompt(
                tool_specs=tool_specs,
                task_context=task_context,
                target_url=target_url
            )
            
            # Prepare messages with templated system prompt
            messages = state["messages"]
            messages_with_system = [SystemMessage(content=system_prompt)] + list(messages)

            # Handle case where model_name is explicitly None (not just missing)
            model_name = config.get("configurable", {}).get("model_name") or "gpt-4o-mini"

            # Get cached bound model
            model = get_cached_bound_model(model_name, tools)

            # Log model binding
            log_model_binding(model_name, len(tools))

            # Invoke the model
            response = await model.ainvoke(messages_with_system)

            # If MCP connection failed, add a note about limited capabilities
            if connection_info["state"] == "failed" and len(state["messages"]) == 1:  # First message
                fallback_notice = (
                    "\n\n*Note: I'm currently operating with limited browser automation tools due to MCP server connectivity. "
                    "I'll automatically regain full capabilities when the connection is restored.*"
                )
                if hasattr(response, "content"):
                    response.content += fallback_notice
                elif hasattr(response, "message"):
                    response.message += fallback_notice

            return {"messages": [response]}

        except Exception as e:
            logger.error(f"❌ Agent error: {type(e).__name__}: {e}")

            # Provide helpful error message to user
            error_message = (
                f"I encountered an error while processing your request: {str(e)}. "
                "This might be due to connectivity issues. Please try again in a moment."
            )

            return {"messages": [AIMessage(content=error_message)]}

    return agent_node


def should_continue(state: PlaywrightAgentState) -> str:
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
