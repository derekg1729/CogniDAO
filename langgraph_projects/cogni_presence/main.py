import asyncio
from utils.build_graph import build_graph

# Module-level export for LangGraph dev server
graph = asyncio.run(build_graph()).compile()
