"""EDO utilities for LangGraph agents - simplified implementation."""

import json
from datetime import datetime
from typing import Dict, Any
from langgraph.types import RunnableConfig
from .logging_utils import get_logger
from .tool_registry import get_tools

logger = get_logger(__name__)


async def edo_event_loader_node(
    state: Dict[str, Any], 
    config: RunnableConfig,
    agent_id: str
) -> Dict[str, Any]:
    """Load unprocessed Events (log blocks with no incoming reason_for links) for specific agent."""
    logger.info("📥 Loading events...")

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
            state.update({"edo_current_event": None, "edo_reasoning_context": []})
            return state

        # Filter by agent_id
        metadata_filters = f'{{"x_agent_id": "{agent_id}"}}'
        result = await get_memory_tool.ainvoke({
            "type_filter": "log", 
            "limit": "1",
            "metadata_filters": metadata_filters
        })
        if isinstance(result, str):
            result = json.loads(result)

        if not (result and result.get("success") and result.get("blocks")):
            logger.warning("No log blocks found")
            state.update({"edo_current_event": None, "edo_reasoning_context": []})
            return state

        blocks = result.get("blocks", [])
        if not blocks:
            state.update({"edo_current_event": None, "edo_reasoning_context": []})
            return state

        # Find unprocessed event
        event_block = None
        for block in blocks:
            if get_linked_tool:
                incoming_links = await get_linked_tool.ainvoke(
                    {
                        "source_block_id": block["id"],
                        "direction_filter": "incoming",
                        "relation_filter": "reason_for",
                        "limit": "1",
                    }
                )
                if isinstance(incoming_links, str):
                    incoming_links = json.loads(incoming_links)

                if incoming_links and incoming_links.get("success"):
                    linked_blocks = incoming_links.get("linked_blocks", [])
                    if not linked_blocks:
                        event_block = block
                        break
            else:
                event_block = block
                break

        if event_block:
            logger.info(f"Found event: {event_block['id']}")
            state["edo_current_event"] = event_block

            # Get context
            if get_linked_tool:
                links_result = await get_linked_tool.ainvoke(
                    {"source_block_id": event_block["id"], "limit": "10"}
                )
                if isinstance(links_result, str):
                    links_result = json.loads(links_result)
                if links_result and links_result.get("success"):
                    state["edo_reasoning_context"] = links_result.get("blocks", [])
            else:
                state["edo_reasoning_context"] = []

        else:
            logger.warning("No unprocessed events found")
            state.update({"edo_current_event": None, "edo_reasoning_context": []})

    except Exception as e:
        logger.error(f"Event loader failed: {e}")
        state.update({"edo_current_event": None, "edo_reasoning_context": []})

    return state


async def next_edo_log_creator_node(
    state: Dict[str, Any], 
    config: RunnableConfig,
    agent_id: str
) -> Dict[str, Any]:
    """Create next EDO log linked to previous log, for agent to write findings into."""
    thread_id = config["configurable"]["thread_id"]
    timestamp = datetime.utcnow().isoformat()
    current_event = state.get("edo_current_event")
    if not current_event:
        return state

    logger.info(f"📝 Creating next EDO log for {current_event['id']}")

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
                "title": f"Analysis: {current_event.get('title', 'Event')}",
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
                        "source_block_id": current_event["id"],
                        "target_block_id": next_log_id,
                        "relation": "reason_for",
                    }
                )
                if isinstance(link_result, str):
                    link_result = json.loads(link_result)

                logger.info(f"✅ Created next EDO log: {current_event['id']} → {next_log_id}")
                state.update({
                    "edo_next_log_id": next_log_id,
                    "edo_next_log": next_log_result.get("block")
                })

    except Exception as e:
        logger.error(f"Next EDO log creation failed: {e}")

    return state


