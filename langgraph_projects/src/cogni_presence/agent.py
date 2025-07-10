"""
CogniDAO Presence Agent - Simple memory management agent using LangGraph's create_react_agent.
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from src.shared_utils import get_logger
from src.shared_utils.tool_specs import generate_tool_specs_from_mcp_tools
from src.shared_utils.tool_registry import get_tools
from .prompts import COGNI_PRESENCE_PROMPT

logger = get_logger(__name__)


async def create_agent_node():
    """Create CogniDAO agent using LangGraph's create_react_agent."""
    # Get tools (MCP client handles all connection logic internally)
    tools = await get_tools("cogni")
    
    # Create prompt with static values using .partial()
    tool_specs = generate_tool_specs_from_mcp_tools(tools)
    prompt = COGNI_PRESENCE_PROMPT.partial(
        tool_specs=tool_specs
    )
    
    # Create and return LangGraph react agent
    model = ChatOpenAI(model_name='gpt-4o-mini')
    return create_react_agent(model=model, tools=tools, prompt=prompt)


def should_continue(state) -> str:
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