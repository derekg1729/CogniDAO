"""
Tool Registry for Phase 2 MCP Auto-Generation

This module collects all existing CogniTool instances and provides them
for auto-generation of MCP tool bindings, eliminating manual wrapper duplication.
"""

from typing import Dict, List
from infra_core.memory_system.tools.base.cogni_tool import CogniTool

# Import all existing CogniTool instances from agent_facing directory
from infra_core.memory_system.tools.agent_facing.add_validation_report_tool import (
    add_validation_report_tool,
)
from infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool import (
    bulk_create_blocks_tool,
)
from infra_core.memory_system.tools.agent_facing.bulk_create_links_tool import (
    bulk_create_links_tool,
)
from infra_core.memory_system.tools.agent_facing.bulk_delete_blocks_tool import (
    bulk_delete_blocks_tool,
)
from infra_core.memory_system.tools.agent_facing.create_block_link_tool import (
    create_block_link_tool,
)
from infra_core.memory_system.tools.agent_facing.create_doc_memory_block_tool import (
    create_doc_memory_block_tool,
)
from infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool import (
    create_memory_block_agent_tool,
)
from infra_core.memory_system.tools.agent_facing.create_work_item_tool import create_work_item_tool
from infra_core.memory_system.tools.agent_facing.delete_memory_block_tool import (
    delete_memory_block_tool_instance,
)
from infra_core.memory_system.tools.agent_facing.get_active_work_items_tool import (
    get_active_work_items_tool,
)
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool_instance,
)
from infra_core.memory_system.tools.agent_facing.get_memory_links_tool import (
    get_memory_links_tool_instance,
)
from infra_core.memory_system.tools.agent_facing.get_linked_blocks_tool import (
    get_linked_blocks_tool_instance,
)
from infra_core.memory_system.tools.agent_facing.get_project_graph_tool import (
    get_project_graph_tool,
)
from infra_core.memory_system.tools.agent_facing.global_memory_inventory_tool import (
    global_memory_inventory_tool,
)
from infra_core.memory_system.tools.agent_facing.global_semantic_search_tool import (
    global_semantic_search_tool,
)
from infra_core.memory_system.tools.agent_facing.health_check_tool import (
    health_check_tool,
)
from infra_core.memory_system.tools.agent_facing.log_interaction_block_tool import (
    log_interaction_block_tool,
)
from infra_core.memory_system.tools.agent_facing.query_doc_memory_block_tool import (
    query_doc_memory_block_tool,
)
from infra_core.memory_system.tools.agent_facing.set_context_tool import set_context_tool
from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
    update_memory_block_tool_instance,
)
from infra_core.memory_system.tools.agent_facing.update_task_status_tool import (
    update_task_status_tool,
)
from infra_core.memory_system.tools.agent_facing.update_work_item_tool import update_work_item_tool

# Note: bulk_update_namespace_tool is also a function, not a CogniTool instance

# Note: Several tools exist as functions but not as CogniTool instances yet:
# - get_active_work_items_tool (function exists, no CogniTool instance)
# - get_linked_blocks_tool (function exists, no CogniTool instance)
# - create_namespace_tool (function exists, no CogniTool instance)
# - list_namespaces_tool (function exists, no CogniTool instance)


def get_all_cogni_tools() -> List[CogniTool]:
    """
    Get all CogniTool instances for MCP auto-generation.

    Returns:
        List of CogniTool instances ready for MCP binding
    """
    tools = []

    # Core memory operations
    if create_memory_block_agent_tool:
        tools.append(create_memory_block_agent_tool)
    if get_memory_block_tool_instance:
        tools.append(get_memory_block_tool_instance)
    if update_memory_block_tool_instance:
        tools.append(update_memory_block_tool_instance)
    if delete_memory_block_tool_instance:
        tools.append(delete_memory_block_tool_instance)

    # Work item operations
    if create_work_item_tool:
        tools.append(create_work_item_tool)
    if update_work_item_tool:
        tools.append(update_work_item_tool)
    if update_task_status_tool:
        tools.append(update_task_status_tool)
    if add_validation_report_tool:
        tools.append(add_validation_report_tool)
    if get_active_work_items_tool:
        tools.append(get_active_work_items_tool)

    # Document operations
    if create_doc_memory_block_tool:
        tools.append(create_doc_memory_block_tool)
    if query_doc_memory_block_tool:
        tools.append(query_doc_memory_block_tool)

    # Link operations
    if get_memory_links_tool_instance:
        tools.append(get_memory_links_tool_instance)
    if create_block_link_tool:
        tools.append(create_block_link_tool)
    if get_linked_blocks_tool_instance:
        tools.append(get_linked_blocks_tool_instance)

    # Bulk operations
    if bulk_create_blocks_tool:
        tools.append(bulk_create_blocks_tool)
    if bulk_create_links_tool:
        tools.append(bulk_create_links_tool)
    if bulk_delete_blocks_tool:
        tools.append(bulk_delete_blocks_tool)
    # Note: bulk_update_namespace_tool is a function, not CogniTool instance

    # Global operations
    if global_memory_inventory_tool:
        tools.append(global_memory_inventory_tool)
    if global_semantic_search_tool:
        tools.append(global_semantic_search_tool)
    if set_context_tool:
        tools.append(set_context_tool)

    # System operations
    if health_check_tool:
        tools.append(health_check_tool)

    # Namespace operations (none have CogniTool instances yet)

    # Interaction logging
    if log_interaction_block_tool:
        tools.append(log_interaction_block_tool)

    # Deprecated tools (included for completeness)
    if get_project_graph_tool:
        tools.append(get_project_graph_tool)

    return tools


def get_cogni_tools_by_name() -> Dict[str, CogniTool]:
    """
    Get all CogniTool instances indexed by their name for easy lookup.

    Returns:
        Dictionary mapping tool names to CogniTool instances
    """
    tools = get_all_cogni_tools()
    return {tool.name: tool for tool in tools}


def get_registry_stats() -> Dict[str, int]:
    """
    Get statistics about the tool registry.

    Returns:
        Dictionary with registry statistics
    """
    tools = get_all_cogni_tools()
    memory_linked = sum(1 for tool in tools if tool.memory_linked)
    non_memory_linked = len(tools) - memory_linked

    return {
        "total_tools": len(tools),
        "memory_linked_tools": memory_linked,
        "non_memory_linked_tools": non_memory_linked,
        "unique_names": len(set(tool.name for tool in tools)),
    }


if __name__ == "__main__":
    # Allow running this module directly for debugging
    tools = get_all_cogni_tools()

    print("Debug: Checking each tool type:")
    for i, tool in enumerate(tools):
        print(f"  {i}: {tool} (type: {type(tool)})")
        if hasattr(tool, "name"):
            print(f"      name: {tool.name}")
        if hasattr(tool, "memory_linked"):
            print(f"      memory_linked: {tool.memory_linked}")
        else:
            print("      ERROR: No memory_linked attribute!")

    print(f"\nTotal tools loaded: {len(tools)}")

    # Only calculate stats if we have valid tools
    try:
        stats = get_registry_stats()
        print("Tool Registry Stats:")
        print(f"  Total tools: {stats['total_tools']}")
        print(f"  Memory-linked: {stats['memory_linked_tools']}")
        print(f"  Non-memory-linked: {stats['non_memory_linked_tools']}")
        print(f"  Unique names: {stats['unique_names']}")
    except Exception as e:
        print(f"Error calculating stats: {e}")
