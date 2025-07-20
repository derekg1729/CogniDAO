"""
EDO Layered Agent - Event-Decision-Outcome pattern with memory-driven hooks.
"""

from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from typing import Dict, Any
from src.shared_utils import get_logger
from src.shared_utils.tool_specs import generate_tool_specs_from_mcp_tools
from src.shared_utils.tool_registry import get_tools
# EDO functionality moved to explicit graph nodes
from .prompts import LAYERED_COGNI_PROMPT

logger = get_logger(__name__)


class ResponseFormat(BaseModel):
    """Response format for the layered agent with flexible JSON structure."""
    result: Dict[str, Any] = {}  # Flexible JSON structure with default empty dict


def pre_model_hook(state) -> None:
    """Stub pre-model hook - EDO logic moved to explicit nodes."""
    print(f"🔵 PRE-MODEL-STUB: Processing {len(state.get('messages', []))} messages")
    return None


def post_model_hook(state) -> None:
    """Stub post-model hook - EDO logic moved to explicit nodes."""
    print(f"🟢 POST-MODEL-STUB: Generated {len(state.get('messages', []))} total messages")
    return None


async def test_tool() -> str:
    """Testing tool for the layered agent."""
    print("🔧 TEST-TOOL: Tool invoked successfully!")
    return "Test tool executed successfully"


async def create_agent_node():
    """Create Layered Cogni agent using LangGraph's create_react_agent with hooks."""
    # Get tools (MCP client handles all connection logic internally)
    tools = await get_tools("cogni")
    
    # Add our test tool
    tools.append(test_tool)
    
    # Create prompt with static values using .partial()
    tool_specs = generate_tool_specs_from_mcp_tools(tools)
    prompt = LAYERED_COGNI_PROMPT.partial(
        tool_specs=tool_specs
    )
    
    # Create model with structured output
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Create and return LangGraph react agent with hooks and response format
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        pre_model_hook=pre_model_hook,
        post_model_hook=post_model_hook,
        response_format=ResponseFormat
    )


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