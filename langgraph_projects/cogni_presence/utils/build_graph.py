from typing import TypedDict, Annotated, Sequence, Literal
import os
import logging

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END, add_messages

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default fallback tools for when MCP is not available
try:
    from langchain_tavily import TavilySearch

    fallback_tools = [TavilySearch(max_results=1)]
except ImportError:
    # Fallback to the deprecated version if langchain_tavily is not installed
    from langchain_community.tools.tavily_search import TavilySearchResults

    fallback_tools = [TavilySearchResults(max_results=1)]

mcp_url = os.getenv("COGNI_MCP_URL", "http://127.0.0.1:24160/sse")

# Remove the problematic module-level await call


def _get_model(model_name: str, tools=None):
    if model_name == "gpt-4o":
        model = ChatOpenAI(temperature=0, model_name="gpt-4o")
    elif model_name == "gpt-4o-mini":
        model = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
    elif model_name == "gpt-3.5-turbo":
        model = ChatOpenAI(temperature=0, model_name="gpt-3.5-turbo-0125")
    else:
        raise ValueError(f"Unsupported model type: {model_name}")

    # Use MCP tools if available, otherwise fallback tools
    tools_to_bind = tools if tools else fallback_tools
    model = model.bind_tools(tools_to_bind)
    return model


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


# Define the function that determines whether to continue or not
def should_continue(state):
    messages = state["messages"]
    last_message = messages[-1]
    # If there are no tool calls, then we finish
    if not last_message.tool_calls:
        return "end"
    # Otherwise if there is, we continue
    else:
        return "continue"


system_prompt = """Be a helpful assistant"""


# Define the config
class GraphConfig(TypedDict):
    model_name: Literal["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]


async def build_graph():
    """Build the LangGraph workflow with MCP tools."""
    # Get MCP tools
    client = MultiServerMCPClient(
        {
            "cogni-mcp": {
                "url": mcp_url,
                "transport": "sse",
            }
        }
    )

    try:
        mcp_tools = await client.get_tools()
        logger.info(f"Successfully connected to MCP server. Got {len(mcp_tools)} tools")
        tools = mcp_tools
    except Exception as e:
        logger.warning(f"Failed to connect to MCP server: {e}. Using fallback tools.")
        tools = fallback_tools

    # Define the function that calls the model
    def call_model(state, config):
        messages = state["messages"]
        messages = [{"role": "system", "content": system_prompt}] + messages
        model_name = config.get("configurable", {}).get("model_name", "gpt-4o-mini")
        model = _get_model(model_name, tools)
        response = model.invoke(messages)
        # We return a list, because this will get added to the existing list
        return {"messages": [response]}

    # Define the function to execute tools
    tool_node = ToolNode(tools)

    # Define a new graph
    workflow = StateGraph(AgentState, config_schema=GraphConfig)

    # Define the two nodes we will cycle between
    workflow.add_node("agent", call_model)
    workflow.add_node("action", tool_node)

    # Set the entrypoint as `agent`
    # This means that this node is the first one called
    workflow.set_entry_point("agent")

    # We now add a conditional edge
    workflow.add_conditional_edges(
        # First, we define the start node. We use `agent`.
        # This means these are the edges taken after the `agent` node is called.
        "agent",
        # Next, we pass in the function that will determine which node is called next.
        should_continue,
        # Finally we pass in a mapping.
        # The keys are strings, and the values are other nodes.
        # END is a special node marking that the graph should finish.
        # What will happen is we will call `should_continue`, and then the output of that
        # will be matched against the keys in this mapping.
        # Based on which one it matches, that node will then be called.
        {
            # If `tools`, then we call the tool node.
            "continue": "action",
            # Otherwise we finish.
            "end": END,
        },
    )

    # We now add a normal edge from `tools` to `agent`.
    # This means that after `tools` is called, `agent` node is called next.
    workflow.add_edge("action", "agent")

    return workflow
