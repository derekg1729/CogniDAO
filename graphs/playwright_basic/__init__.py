"""
Playwright Basic LangGraph Package
==================================

A LangGraph implementation for browser automation using Playwright MCP tools.
"""

from .graph import compile_graph, create_stategraph, PlaywrightState

__version__ = "0.1.0"
__all__ = ["compile_graph", "create_stategraph", "PlaywrightState"]
