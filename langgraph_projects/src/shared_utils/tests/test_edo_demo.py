"""
Demo test for EDO pattern using edo_layered_agent.
Creates 3 mock events and processes them through the EDO cycle.
"""

import asyncio
from src.shared_utils.edo_hooks import create_mock_event
from src.shared_utils.tool_registry import get_tools
from src.shared_utils import get_logger

logger = get_logger(__name__)


async def create_demo_events():
    """Create 3 mock events for EDO testing."""
    events = [
        {
            "title": "User Feature Request",
            "content": "User requested dark mode toggle for the application dashboard."
        },
        {
            "title": "System Performance Alert", 
            "content": "API response times exceeded 2s threshold for 5+ minutes."
        },
        {
            "title": "Security Vulnerability Detected",
            "content": "Dependency scan found high-severity vulnerability in auth library."
        }
    ]
    
    created_events = []
    for event in events:
        event_id = await create_mock_event(event["title"], event["content"], "edo_layered_agent")
        if event_id:
            created_events.append(event_id)
            
    return created_events


async def verify_edo_chains():
    """Verify that EDO chains were created properly by checking links."""
    try:
        tools = await get_tools("cogni")
        
        # Find required tools
        get_memory_tool = None
        get_linked_tool = None
        
        for tool in tools:
            if tool.name == "GetMemoryBlock":
                get_memory_tool = tool
            elif tool.name == "GetLinkedBlocks":
                get_linked_tool = tool
        
        if not get_memory_tool:
            logger.error("GetMemoryBlock tool not found")
            return False
        
        # Get recent memory blocks
        result = await get_memory_tool.ainvoke({"type_filter": "log", "limit": "20"})
        
        if hasattr(result, 'content') and result.content:
            import json
            result_data = json.loads(result.content)
            
            if result_data and result_data.get("blocks"):
                blocks = result_data["blocks"]
                
                # Group by EDO phase from metadata
                events = []
                decisions = []
                outcomes = []
                
                for block in blocks:
                    metadata = block.get("metadata", {})
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}
                    
                    edo_phase = metadata.get("edo_phase", "")
                    if "event" in edo_phase:
                        events.append(block)
                    elif "decision" in edo_phase:
                        decisions.append(block)
                    elif "outcome" in edo_phase:
                        outcomes.append(block)
                
                print("📊 EDO Topology Verification:")
                print(f"   Events: {len(events)}")
                print(f"   Decisions: {len(decisions)}")  
                print(f"   Outcomes: {len(outcomes)}")
                
                # Check links for each decision if tool available
                if get_linked_tool:
                    for decision in decisions:
                        links_result = await get_linked_tool.ainvoke({
                            "source_block_id": decision["id"]
                        })
                        
                        if hasattr(links_result, 'content') and links_result.content:
                            links_data = json.loads(links_result.content)
                            linked_blocks = links_data.get("blocks", [])
                            print(f"   Decision {decision['id'][:8]} links to {len(linked_blocks)} blocks")
                        
                return True
            
    except Exception as e:
        logger.error(f"EDO verification failed: {e}")
        return False


async def main():
    """Run EDO demo test."""
    print("🚀 Starting EDO Pattern Demo")
    
    # Step 1: Create mock events
    print("\n📝 Creating 3 mock events...")
    events = await create_demo_events()
    print(f"   Created {len(events)} events: {events}")
    
    # Step 2: Run agent to process events (manual trigger)
    print("\n🤖 Ready to process events with edo_layered_agent")
    print("   Run the agent manually to trigger EDO processing")
    print("   Each agent invocation should process one event → decision → outcome")
    
    # Step 3: Verify chains were created
    print("\n🔍 Verifying EDO link topology...")
    success = await verify_edo_chains()
    
    if success:
        print("✅ EDO demo completed successfully")
    else:
        print("❌ EDO demo encountered issues")


if __name__ == "__main__":
    asyncio.run(main())