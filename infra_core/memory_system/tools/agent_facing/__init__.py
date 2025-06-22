"""
Agent-facing tools for memory system operations.

These tools provide simplified interfaces for agents to work with the memory system.
"""

# Import all agent-facing tools here to register them
from .create_doc_memory_block_tool import create_doc_memory_block_tool
from .query_doc_memory_block_tool import query_doc_memory_block_tool
from .get_memory_block_tool import get_memory_block_tool
from .get_memory_links_tool import get_memory_links_tool
from .get_linked_blocks_tool import get_linked_blocks_tool
from .log_interaction_block_tool import log_interaction_block_tool
from .add_validation_report_tool import add_validation_report_tool
from .create_work_item_tool import create_work_item_tool
from .update_task_status_tool import update_task_status_tool
from .get_active_work_items_tool import get_active_work_items_tool
from .update_work_item_tool import update_work_item_tool
from .create_block_link_tool import create_block_link_agent
from .bulk_create_blocks_tool import bulk_create_blocks_tool
from .bulk_create_links_tool import bulk_create_links_tool
from .bulk_delete_blocks_tool import bulk_delete_blocks_tool
from .bulk_update_namespace_tool import bulk_update_namespace_tool

# Export all tools to make them available
__all__ = [
    "create_doc_memory_block_tool",
    "query_doc_memory_block_tool",
    "get_memory_block_tool",
    "get_memory_links_tool",
    "get_linked_blocks_tool",
    "log_interaction_block_tool",
    "add_validation_report_tool",
    "create_work_item_tool",
    "update_task_status_tool",
    "get_active_work_items_tool",
    "update_work_item_tool",
    "create_block_link_agent",
    "bulk_create_blocks_tool",
    "bulk_create_links_tool",
    "bulk_delete_blocks_tool",
    "bulk_update_namespace_tool",
]
