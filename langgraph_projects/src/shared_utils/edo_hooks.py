"""EDO utilities for LangGraph agents - simplified implementation."""

import json
from datetime import datetime
from typing import Dict, Any, Optional
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


async def edo_decision_writer_node(
    state: Dict[str, Any], 
    config: RunnableConfig,
    agent_id: str
) -> Dict[str, Any]:
    """Write Decision and Outcome blocks with agent metadata, create EDO links."""
    thread_id = config["configurable"]["thread_id"]
    timestamp = datetime.utcnow().isoformat()
    current_event = state.get("edo_current_event")
    if not current_event:
        return state

    logger.info(f"📤 Writing decision for {current_event['id']}")

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

        decision_content = getattr(state.get("messages", [{}])[-1], "content", "No decision")

        # Create Decision
        decision_result = await create_memory_tool.ainvoke(
            {
                "type": "log",
                "content": decision_content,
                "title": f"Decision: {current_event.get('title', 'Event')}",
                "metadata": f'{{"edo_phase": "decision", "actor": "edo_agent", "x_agent_id": "{agent_id}", "x_thread_id": "{thread_id}", "x_timestamp": "{timestamp}"}}',
            }
        )
        if isinstance(decision_result, str):
            decision_result = json.loads(decision_result)

        if decision_result and decision_result.get("success"):
            decision_id = decision_result.get("block_id")
            if decision_id:
                # Link Event → Decision
                link_result = await create_link_tool.ainvoke(
                    {
                        "source_block_id": current_event["id"],
                        "target_block_id": decision_id,
                        "relation": "reason_for",
                    }
                )
                if isinstance(link_result, str):
                    link_result = json.loads(link_result)

                # Create Outcome
                outcome_result = await create_memory_tool.ainvoke(
                    {
                        "type": "log",
                        "content": "Outcome pending...",
                        "title": f"Outcome: {current_event.get('title', 'Event')}",
                        "metadata": f'{{"edo_phase": "outcome", "actor": "pending", "x_agent_id": "{agent_id}", "x_thread_id": "{thread_id}", "x_timestamp": "{timestamp}"}}',
                    }
                )
                if isinstance(outcome_result, str):
                    outcome_result = json.loads(outcome_result)

                if outcome_result and outcome_result.get("success"):
                    outcome_id = outcome_result.get("block_id")
                    if outcome_id:
                        # Link Decision → Outcome
                        link_result2 = await create_link_tool.ainvoke(
                            {
                                "source_block_id": decision_id,
                                "target_block_id": outcome_id,
                                "relation": "causes",
                            }
                        )
                        if isinstance(link_result2, str):
                            link_result2 = json.loads(link_result2)

                        logger.info(
                            f"✅ EDO chain: {current_event['id']} → {decision_id} → {outcome_id}"
                        )
                        state.update({"edo_decision_id": decision_id, "edo_outcome_id": outcome_id})

    except Exception as e:
        logger.error(f"Decision writer failed: {e}")

    return state


async def create_mock_event(title: str, content: str) -> Optional[str]:
    """Create mock event for testing."""
    try:
        tools = await get_tools("cogni")
        create_tool = next(
            (t for t in tools if hasattr(t, "name") and t.name == "CreateMemoryBlock"), None
        )

        if not create_tool:
            return None

        result = await create_tool.ainvoke(
            {
                "type": "log",
                "content": content,
                "title": title,
                "metadata": f'{{"x_agent_id": "system", "component": "edo_agent", "x_timestamp": "{datetime.utcnow().isoformat()}"}}'
            }
        )
        if isinstance(result, str):
            result = json.loads(result)

        if result and result.get("success"):
            block_id = result.get("block_id")
            if block_id:
                logger.info(f"📝 Created event: {block_id}")
                return block_id
    except Exception as e:
        logger.error(f"Mock event creation failed: {e}")

    return None
