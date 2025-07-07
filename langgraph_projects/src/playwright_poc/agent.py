"""
Playwright Basic Agent Nodes.

Agent logic and node functions for the Playwright browser automation graph.
"""

from collections.abc import Callable

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from src.shared_utils import (
    PlaywrightAgentState,
    get_cached_bound_model,
    get_logger,
    get_mcp_tools,
    log_model_binding,
)

logger = get_logger(__name__)


def create_agent_nodes(tools: list[BaseTool]) -> tuple[Callable, Callable, Callable]:
    """
    Create all agent node functions for the Playwright graph.

    Args:
        tools: List of Playwright MCP tools

    Returns:
        Tuple of (setup_node, agent_node, tool_node) functions
    """

    async def setup_agent_node(state: PlaywrightAgentState) -> PlaywrightAgentState:
        """
        Node to set up the agent with MCP tools.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with tools availability
        """
        try:
            # Verify MCP tools can be obtained (validation check)
            await get_mcp_tools(server_type="playwright")

            # Check if tools are available and set flag
            return {**state, "tools_available": True, "messages": state["messages"]}

        except Exception as e:
            logger.error(f"❌ Failed to setup agent: {e}")
            return {
                **state,
                "tools_available": False,
                "messages": state["messages"] + [AIMessage(content=f"Error setting up tools: {e}")],
            }

    async def agent_node(state: PlaywrightAgentState) -> PlaywrightAgentState:
        """
        Main agent reasoning node.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with model response
        """
        if not state.get("tools_available", False):
            return {
                **state,
                "messages": state["messages"]
                + [AIMessage(content="Tools not available. Please check MCP server connection.")],
            }

        # Get the latest human message
        if not state["messages"]:
            return {
                **state,
                "messages": [AIMessage(content="No messages to process.")],
            }

        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            return state

        try:
            # Get cached bound model
            model = get_cached_bound_model("gpt-4o-mini", tools)

            # Log model binding
            log_model_binding("gpt-4o-mini", len(tools))

            # Invoke the agent
            response = await model.ainvoke(state["messages"])

            return {
                **state,
                "messages": state["messages"] + [response],
                "current_task": last_message.content,
            }

        except Exception as e:
            logger.error(f"❌ Agent error: {e}")
            return {
                **state,
                "messages": state["messages"]
                + [AIMessage(content=f"Error processing request: {e}")],
            }

    async def tool_execution_node(state: PlaywrightAgentState) -> PlaywrightAgentState:
        """
        Execute tool calls.

        Args:
            state: Current agent state

        Returns:
            Updated agent state with tool results
        """
        last_message = state["messages"][-1]

        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return state

        try:
            # Create tool map
            tool_map = {tool.name: tool for tool in tools}
            tool_messages = []

            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]

                if tool_name in tool_map:
                    tool = tool_map[tool_name]
                    try:
                        result = await tool.ainvoke(tool_args)
                        tool_messages.append(
                            {
                                "role": "tool",
                                "content": str(result),
                                "tool_call_id": tool_call["id"],
                            }
                        )
                    except Exception as e:
                        tool_messages.append(
                            {
                                "role": "tool",
                                "content": f"Error executing {tool_name}: {e}",
                                "tool_call_id": tool_call["id"],
                            }
                        )

            return {**state, "messages": state["messages"] + tool_messages}

        except Exception as e:
            logger.error(f"❌ Tool execution error: {e}")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"Tool execution failed: {e}")],
            }

    return setup_agent_node, agent_node, tool_execution_node


def should_continue(state: PlaywrightAgentState) -> str:
    """
    Determine if we should continue or end.

    Args:
        state: Current agent state

    Returns:
        Either "tools" or END
    """
    last_message = state["messages"][-1]

    # If the last message has tool calls, continue to tool execution
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise, we're done
    return "end"
