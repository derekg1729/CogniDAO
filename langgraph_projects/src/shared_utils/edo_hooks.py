"""EDO utilities for LangGraph agents - simplified implementation."""

import json
from datetime import datetime, timezone
from typing import Dict, Any
from langgraph.types import RunnableConfig
from .logging_utils import get_logger
from .tool_registry import get_tools
from .state_types import PREV_EDO, CURR_EDO

logger = get_logger(__name__)


async def edo_event_loader_node(
    state: Dict[str, Any], 
    config: RunnableConfig,
    agent_id: str
) -> Dict[str, Any]:
    """Load unprocessed Events (log blocks with no outgoing reason_for links) for specific agent."""
    logger.info("📥 Loading events...")
    
    # Skip if memory refs already populated (avoid re-execution on every message)
    memory_refs = state.get("relevant_memory_block_refs", {})
    if memory_refs.get(PREV_EDO):
        logger.info("📝 Previous EDO log already loaded, skipping event loader")
        return state

    try:
        tools = await get_tools("cogni")
        get_memory_tool = next(
            (t for t in tools if hasattr(t, "name") and t.name == "GetMemoryBlock"), None
        )
        get_linked_tool = next(
            (t for t in tools if hasattr(t, "name") and t.name == "GetLinkedBlocks"), None
        )

        if not get_memory_tool:
            logger.error("GetMemoryBlock tool not found")
            return state

        # Filter by agent_id
        metadata_filters = f'{{"x_agent_id": "{agent_id}"}}'
        # Note: Removed limit to work around GetMemoryBlock tool limitation
        # The tool lacks ordering parameters, so limit=1 returns oldest, not newest
        result = await get_memory_tool.ainvoke({
            "type_filter": "log", 
            "metadata_filters": metadata_filters
        })
        if isinstance(result, str):
            result = json.loads(result)

        if not (result and result.get("success") and result.get("blocks")):
            logger.warning("No log blocks found")
            return state

        blocks = result.get("blocks", [])
        if not blocks:
            return state

        # Find unprocessed event (most recent log with no outgoing "reason_for" links)
        event_block = None
        for block in blocks:
            if get_linked_tool:
                outgoing_links = await get_linked_tool.ainvoke(
                    {
                        "source_block_id": block["id"],
                        "direction_filter": "outgoing",
                        "relation_filter": "reason_for",
                        "limit": "1",
                    }
                )
                if isinstance(outgoing_links, str):
                    outgoing_links = json.loads(outgoing_links)

                if outgoing_links and outgoing_links.get("success"):
                    linked_blocks = outgoing_links.get("linked_blocks", [])
                    if not linked_blocks:
                        event_block = block
                        break
            else:
                event_block = block
                break

        if event_block:
            logger.info(f"Found event: {event_block['id']}")
            # Add previous agent's EDO log to memory refs
            state.setdefault("relevant_memory_block_refs", {})[PREV_EDO] = event_block["id"]

            # Get context blocks and add to memory refs
            if get_linked_tool:
                links_result = await get_linked_tool.ainvoke(
                    {"source_block_id": event_block["id"], "limit": "10"}
                )
                if isinstance(links_result, str):
                    links_result = json.loads(links_result)
                if links_result and links_result.get("success"):
                    context_blocks = links_result.get("blocks", [])
                    # Add each context block to memory refs with numbered names
                    for i, block in enumerate(context_blocks):
                        if "id" in block:
                            state.setdefault("relevant_memory_block_refs", {})[f"context_block_{i+1}"] = block["id"]

        else:
            logger.warning("No unprocessed events found")

    except Exception as e:
        logger.error(f"Event loader failed: {e}")

    return state


async def next_edo_log_creator_node(
    state: Dict[str, Any], 
    config: RunnableConfig,
    agent_id: str
) -> Dict[str, Any]:
    """Create next EDO log linked to previous log, for agent to write findings into."""
    # Skip if current EDO log already exists (avoid re-execution on every message)
    memory_refs = state.get("relevant_memory_block_refs", {})
    if memory_refs.get(CURR_EDO):
        logger.info("📝 Current EDO log already created, skipping creator")
        return state
    
    thread_id = config["configurable"]["thread_id"]
    timestamp = datetime.now(timezone.utc).isoformat()
    # Get previous agent's log ID from memory refs
    past_log_id = memory_refs.get(PREV_EDO)
    
    if not past_log_id:
        logger.warning("No previous agent EDO log found in memory refs")
        return state

    logger.info(f"📝 Creating next EDO log for {past_log_id}")

    try:
        tools = await get_tools("cogni")
        create_memory_tool = next(
            (t for t in tools if hasattr(t, "name") and t.name == "CreateMemoryBlock"), None
        )
        create_link_tool = next(
            (t for t in tools if hasattr(t, "name") and t.name == "CreateBlockLink"), None
        )

        if not create_memory_tool or not create_link_tool:
            logger.error("Required tools not found")
            return state

        # Create blank next EDO log for agent to write into
        next_log_result = await create_memory_tool.ainvoke(
            {
                "type": "log",
                "content": "Agent analysis and findings will be written here...",
                "title": f"{agent_id} log {thread_id}",
                "x_agent_id": agent_id,
                "x_timestamp": timestamp,
                "x_thread_id": thread_id,
            }
        )
        if isinstance(next_log_result, str):
            next_log_result = json.loads(next_log_result)
        
        logger.info(f"🔍 Next log creation result: {next_log_result}")

        if next_log_result and next_log_result.get("success"):
            next_log_id = next_log_result.get("id")
            if next_log_id:
                # Link Previous Event → Next Log
                link_result = await create_link_tool.ainvoke(
                    {
                        "source_block_id": past_log_id,
                        "target_block_id": next_log_id,
                        "relation": "reason_for",
                    }
                )
                if isinstance(link_result, str):
                    link_result = json.loads(link_result)

                logger.info(f"✅ Created next EDO log: {past_log_id} → {next_log_id}")
                # Add current agent log to memory refs
                state.setdefault("relevant_memory_block_refs", {})[CURR_EDO] = next_log_id

    except Exception as e:
        logger.error(f"Next EDO log creation failed: {e}")

    return state


