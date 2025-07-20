"""
CogniDAO Presence Agent - Main Entry Point

This module provides the main entry point for the CogniDAO Presence Agent
for LangGraph deployment and development server.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

# Import after path setup to satisfy linting
from src.layered_cogni_agent.graph import build_compiled_graph  # noqa: E402

# Export compiled graph for LangGraph deployment
try:
    # Check if we're already in an event loop
    loop = asyncio.get_running_loop()
    # If we're here, there's already a loop running
    # Create graph synchronously for import scenarios
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(asyncio.run, build_compiled_graph())
        graph = future.result()
except RuntimeError:
    # No event loop running, safe to create one
    graph = asyncio.run(build_compiled_graph())
