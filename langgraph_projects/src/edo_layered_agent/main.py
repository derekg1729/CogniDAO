"""
EDO Layered Agent - Main Entry Point

This module provides the main entry point for the EDO Layered Agent
for LangGraph deployment and development server.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Import after path setup to satisfy linting
from src.edo_layered_agent.graph import build_compiled_graph  # noqa: E402


# No event loop running, safe to create one
graph = asyncio.run(build_compiled_graph())
