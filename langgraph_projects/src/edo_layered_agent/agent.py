"""
EDO Layered Agent - Event-Decision-Outcome pattern with memory-driven hooks.
"""

import json
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from pydantic import BaseModel
from typing import Dict, Any
from src.shared_utils import get_logger
from src.shared_utils.tool_specs import generate_tool_specs_from_mcp_tools
from src.shared_utils.tool_registry import get_tools
from src.shared_utils.edo_tools import write_handoff_summary
from src.edo_layered_agent.state_types import CogniAgentState

# EDO functionality moved to explicit graph nodes
from .prompts import EDO_PROTOTYPE_AGENT_PROMPT

logger = get_logger(__name__)


class ResponseFormat(BaseModel):
    """Response format for the layered agent with flexible JSON structure."""

    result: Dict[str, Any] = {}  # Flexible JSON structure with default empty dict


def pre_model_hook(state):
    """Inject EDO context as SystemMessage before each LLM call."""
    # Get EDO context from state
    edo_context = state.get("edo_current_event", {})

    # Create SystemMessage with EDO context
    if edo_context:
        system_msg = SystemMessage(content=f"EDO Context: {json.dumps(edo_context, indent=2)}")
        # Return llm_input_messages to inject context without modifying stored history
        return {"llm_input_messages": [system_msg] + state["messages"]}

    # If no EDO context, just pass through normal messages
    return {"llm_input_messages": state["messages"]}


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

    # Add our test tool and EDO handoff tool
    tools.append(test_tool)
    tools.append(write_handoff_summary)

    # Create prompt with static values using .partial()
    tool_specs = generate_tool_specs_from_mcp_tools(tools)
    prompt = EDO_PROTOTYPE_AGENT_PROMPT.partial(tool_specs=tool_specs)

    # Create model with structured output
    model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Create and return LangGraph react agent with hooks and response format
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        pre_model_hook=pre_model_hook,
        # post_model_hook=post_model_hook,
        response_format=ResponseFormat,
        state_schema=CogniAgentState,
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
