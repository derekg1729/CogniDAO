"""
EDO (Event-Decision-Outcome) utilities for LangGraph agents.
Implements memory-driven EDO pattern with explicit nodes and stub hooks.
"""

from typing import Dict, Any, Optional
from .logging_utils import get_logger
from .tool_registry import get_tools

logger = get_logger(__name__)


async def edo_event_loader_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    EDO Event Loader Node - retrieve current Event to process.
    
    Finds unprocessed events and loads reasoning context into state.
    Sets state['edo_current_event'] and state['edo_reasoning_context'].
    """
    print("📥 EDO-EVENT-LOADER: Loading unprocessed events")
    
    try:
        # Get MCP tools
        tools = await get_tools("cogni")
        
        # Find GetMemoryBlock tool
        get_memory_tool = None
        get_linked_tool = None
        
        for tool in tools:
            if hasattr(tool, 'name'):
                if tool.name == "GetMemoryBlock":
                    get_memory_tool = tool
                elif tool.name == "GetLinkedBlocks":
                    get_linked_tool = tool
        
        if not get_memory_tool:
            logger.error("GetMemoryBlock tool not found")
            state['edo_current_event'] = None
            state['edo_reasoning_context'] = []
            return state
        
        # Find unprocessed events (log blocks)
        result = await get_memory_tool.ainvoke({"type_filter": "log", "limit": "1"})
        
        if hasattr(result, 'content') and result.content:
            # Parse tool result content
            import json
            result_data = json.loads(result.content)
            
            if result_data and result_data.get("blocks"):
                event_block = result_data["blocks"][0]
                print(f"📥 EDO-EVENT-LOADER: Found event {event_block['id']}: {event_block.get('title', 'No title')}")
                
                # Store event context in state
                state['edo_current_event'] = event_block
                
                # Get linked context if tool available
                if get_linked_tool:
                    links_result = await get_linked_tool.ainvoke({
                        "source_block_id": event_block['id'], 
                        "limit": "10"
                    })
                    
                    if hasattr(links_result, 'content') and links_result.content:
                        links_data = json.loads(links_result.content)
                        state['edo_reasoning_context'] = links_data.get("blocks", [])
                        print(f"📥 EDO-EVENT-LOADER: Loaded {len(state.get('edo_reasoning_context', []))} context blocks")
                else:
                    state['edo_reasoning_context'] = []
            else:
                print("📥 EDO-EVENT-LOADER: No events to process")
                state['edo_current_event'] = None
                state['edo_reasoning_context'] = []
        else:
            print("📥 EDO-EVENT-LOADER: No events found")
            state['edo_current_event'] = None
            state['edo_reasoning_context'] = []
            
    except Exception as e:
        logger.error(f"EDO event loader failed: {e}")
        state['edo_current_event'] = None
        state['edo_reasoning_context'] = []
    
    return state


async def edo_decision_writer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    EDO Decision Writer Node - write Decision block and create links.
    
    Creates Decision block, links Event reason_for Decision, and Decision causes Outcome.
    """
    print("📤 EDO-DECISION-WRITER: Writing decision and outcome blocks")
    
    # Only process if we had an event to decide on
    current_event = state.get('edo_current_event')
    if not current_event:
        print("📤 EDO-DECISION-WRITER: No event to process, skipping")
        return state
        
    try:
        # Get MCP tools
        tools = await get_tools("cogni")
        
        # Find required tools
        create_memory_tool = None
        create_link_tool = None
        
        for tool in tools:
            if hasattr(tool, 'name'):
                if tool.name == "CreateMemoryBlock":
                    create_memory_tool = tool
                elif tool.name == "CreateBlockLink":
                    create_link_tool = tool
        
        if not create_memory_tool or not create_link_tool:
            logger.error("Required tools not found")
            return state
        
        # Extract decision from agent's last message
        if state.get('messages'):
            last_msg = state['messages'][-1]
            decision_content = getattr(last_msg, 'content', 'No decision recorded')
            
            print(f"📤 EDO-DECISION-WRITER: Creating decision for event {current_event['id']}")
            
            # Create Decision block
            decision_result = await create_memory_tool.ainvoke({
                "type": "log",
                "content": decision_content,
                "title": f"Decision for: {current_event.get('title', 'Event')}",
                "metadata": '{"edo_phase": "decision", "actor": "edo_agent"}'
            })
            
            if hasattr(decision_result, 'content') and decision_result.content:
                import json
                decision_data = json.loads(decision_result.content)
                decision_id = decision_data.get("block_id")
                
                if decision_id:
                    print(f"📤 EDO-DECISION-WRITER: Created decision block {decision_id}")
                    
                    # Link: Event reason_for Decision
                    await create_link_tool.ainvoke({
                        "source_block_id": current_event['id'],
                        "target_block_id": decision_id,
                        "relation": "reason_for"
                    })
                    
                    # Create Outcome placeholder
                    outcome_result = await create_memory_tool.ainvoke({
                        "type": "log",
                        "content": "Outcome pending...",
                        "title": f"Outcome for: {current_event.get('title', 'Event')}",
                        "metadata": '{"edo_phase": "outcome", "actor": "pending"}'
                    })
                    
                    if hasattr(outcome_result, 'content') and outcome_result.content:
                        outcome_data = json.loads(outcome_result.content)
                        outcome_id = outcome_data.get("block_id")
                        
                        if outcome_id:
                            # Link: Decision causes Outcome
                            await create_link_tool.ainvoke({
                                "source_block_id": decision_id,
                                "target_block_id": outcome_id,
                                "relation": "causes"
                            })
                            
                            print(f"📤 EDO-DECISION-WRITER: Completed EDO chain: {current_event['id']} → {decision_id} → {outcome_id}")
                            
                            # Store results in state
                            state['edo_decision_id'] = decision_id
                            state['edo_outcome_id'] = outcome_id
                    
    except Exception as e:
        logger.error(f"EDO decision writer failed: {e}")
    
    return state


async def create_mock_event(title: str, content: str) -> Optional[str]:
    """
    Helper function to create mock events for testing EDO pattern.
    
    Args:
        title: Event title
        content: Event description
        
    Returns:
        Block ID of created event or None if failed
    """
    try:
        tools = await get_tools("cogni")
        
        # Find CreateMemoryBlock tool
        create_tool = None
        for tool in tools:
            if tool.name == "CreateMemoryBlock":
                create_tool = tool
                break
        
        if not create_tool:
            logger.error("CreateMemoryBlock tool not found")
            return None
        
        result = await create_tool.ainvoke({
            "type": "log",
            "content": content,
            "title": title,
            "metadata": '{"edo_phase": "event", "actor": "system"}'
        })
        
        if hasattr(result, 'content') and result.content:
            import json
            result_data = json.loads(result.content)
            block_id = result_data.get("block_id")
            
            if block_id:
                print(f"📝 Created mock event: {block_id} - {title}")
                return block_id
            
    except Exception as e:
        logger.error(f"Failed to create mock event: {e}")
        
    return None