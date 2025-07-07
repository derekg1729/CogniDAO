from typing import TypedDict, Annotated, Sequence, Literal
import os
import logging
import asyncio
from functools import lru_cache

from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END, add_messages

logger = logging.getLogger(__name__)

# Default fallback tools for when MCP is not available
try:
    from langchain_tavily import TavilySearch

    fallback_tools = [TavilySearch(max_results=1)]
except ImportError:
    # Fallback to the deprecated version if langchain_tavily is not installed
    from langchain_community.tools.tavily_search import TavilySearchResults

    fallback_tools = [TavilySearchResults(max_results=1)]

mcp_url = os.getenv("COGNI_MCP_URL", "http://toolhive:24160/sse")

ALLOWED_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]


def _create_tools_signature(tools):
    """Create a deterministic signature for tools to use as cache key."""
    return ",".join(sorted(getattr(t, "name", t.__class__.__name__) for t in tools))


@lru_cache(maxsize=32)
def _get_bound_model(model_name: str, tools_signature: str):
    """Get cached model instance with tools already bound.

    Args:
        model_name: Name of the model to create
        tools_signature: Deterministic signature for cache key
    """
    # Map model names to their actual OpenAI model identifiers
    model_mapping = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
    }

    if model_name not in model_mapping:
        raise ValueError(f"Unsupported model {model_name}; choose from {ALLOWED_MODELS}")

    # Enable token-level streaming so downstream SSE emits deltas
    base_model = ChatOpenAI(temperature=0, model_name=model_mapping[model_name], streaming=True)

    # Use global tools for binding (ensures consistency with signature)
    global _tools
    tools_to_bind = _tools if _tools else fallback_tools
    return base_model.bind_tools(tools_to_bind)


def _get_cached_bound_model(model_name: str, tools):
    """Get a fully-bound model with tools, using caching for performance."""
    # Update global tools if provided
    global _tools
    if tools:
        _tools = tools

    tools_to_bind = _tools if _tools else fallback_tools
    tools_signature = _create_tools_signature(tools_to_bind)

    # Only pass hashable signature to cached function
    return _get_bound_model(model_name, tools_signature)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# Define the function that determines whether to continue or not
def should_continue(state):
    messages = state["messages"]

    # Guard against empty messages
    if not messages:
        return "end"

    last_message = messages[-1]

    # Robust check for tool calls
    tool_calls = getattr(last_message, "tool_calls", None)
    if tool_calls:
        return "continue"
    else:
        return "end"


system_prompt = """You are a helpful **CogniDAO assistant** 🤖 

**Primary Tools:** 
- 📋 `GetActiveWorkItems` - Show current tasks
- 🔍 `GlobalSemanticSearch` - Find relevant information  
- 📊 `GlobalMemoryInventory` - Browse memory blocks

**Response Style:**
✅ **Concise** answers with strategic emojis  
📝 Use `code blocks` for tool names  
🎯 Structure with **bold headers** when helpful

**Important:** Leave branch/namespace parameters empty in tool calls."""


# Define the config
class GraphConfig(TypedDict):
    model_name: Literal["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]


# Global tools cache
_tools = None
_tools_lock = asyncio.Lock()


async def _initialize_tools():
    """Initialize MCP tools with fallback."""
    global _tools

    # Check if already initialized (fast path)
    if _tools is not None:
        return _tools

    # Use lock to prevent race conditions
    async with _tools_lock:
        # Double-check pattern
        if _tools is not None:
            return _tools

        # Log the exact URL being used for connection
        logger.info(f"Attempting MCP connection to: {mcp_url}")

        client = MultiServerMCPClient(
            {
                "cogni-mcp": {
                    "url": mcp_url,
                    "transport": "sse",
                }
            }
        )

        try:
            logger.info("Starting MCP client initialization...")
            # Add timeout to prevent hanging during MCP initialization
            mcp_tools = await asyncio.wait_for(client.get_tools(), timeout=30.0)
            logger.info(f"Successfully connected to MCP server. Got {len(mcp_tools)} tools")
            _tools = mcp_tools
        except asyncio.TimeoutError:
            logger.warning(
                "MCP server connection timed out after 30 seconds. Using fallback tools."
            )
            _tools = fallback_tools
        except Exception as e:
            # Log the full exception details for debugging
            logger.error(f"Failed to connect to MCP server at {mcp_url}: {type(e).__name__}: {e}")
            logger.error(f"Exception details: {repr(e)}")
            import traceback

            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.warning("Using fallback tools due to MCP connection failure.")
            _tools = fallback_tools

        return _tools


async def call_model(state, config):
    """Call the model with MCP tools."""
    tools = await _initialize_tools()
    messages = state["messages"]
    messages = [SystemMessage(content=system_prompt)] + messages

    # Handle case where model_name is explicitly None (not just missing)
    model_name = config.get("configurable", {}).get("model_name") or "gpt-4o-mini"

    # Get cached bound model (eliminates repeated bind_tools calls)
    model = _get_cached_bound_model(model_name, tools)

    response = await model.ainvoke(messages)
    return {"messages": [response]}


async def build_graph():
    """Build the LangGraph workflow with MCP tools.

    Returns:
        StateGraph: An uncompiled StateGraph instance.
        Call .compile() on the result to get a runnable graph.

    Example:
        workflow = await build_graph()
        app = workflow.compile()
        result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    tools = await _initialize_tools()

    workflow = StateGraph(AgentState, config_schema=GraphConfig)
    workflow.add_node("agent", call_model)
    workflow.add_node("action", ToolNode(tools))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END,
        },
    )
    workflow.add_edge("action", "agent")

    return workflow


async def build_compiled_graph():
    """Build and compile the LangGraph workflow with MCP tools.

    Returns:
        CompiledStateGraph: A compiled, ready-to-use graph instance.

    Example:
        app = await build_compiled_graph()
        result = await app.ainvoke({"messages": [HumanMessage("Hello")]})
    """
    workflow = await build_graph()
    return workflow.compile()
