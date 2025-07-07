"""
Playwright LangGraph Package.

A LangGraph implementation for browser automation using Playwright MCP tools.
"""

from .agent import create_agent_node, should_continue
from .graph import build_compiled_graph, build_graph

__version__ = "0.1.0"
__all__ = ["build_graph", "build_compiled_graph", "create_agent_node", "should_continue"]
