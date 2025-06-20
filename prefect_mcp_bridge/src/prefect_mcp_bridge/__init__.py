"""
Prefect MCP Bridge Package

Expose MCP HTTP endpoints as reusable Prefect @task wrappers so any flow can
trigger Dolt (and future) operations without shell scripts.
"""

__version__ = "0.1.0"

from .client import MCPClient
from .dolt import dolt_add_task, dolt_commit_task, dolt_push_task, dolt_add_commit_push_task

__all__ = [
    "MCPClient",
    "dolt_add_task",
    "dolt_commit_task",
    "dolt_push_task",
    "dolt_add_commit_push_task",
]
