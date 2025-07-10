"""
CogniDAO Org Chart Package.

A LangGraph supervisor implementation for CogniDAO with CEO and VP agents.
"""

from .graph import build_compiled_graph, build_graph

__version__ = "0.1.0"
__all__ = ["build_graph", "build_compiled_graph"]
