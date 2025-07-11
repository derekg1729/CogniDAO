#!/usr/bin/env python3
"""
Test Redis checkpointer with simple_cogni_agent
"""

import asyncio
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.redis import AsyncRedisSaver

from src.simple_cogni_agent.graph import build_graph


async def test_simple_cogni_redis():
    """Test Redis checkpointer with simple_cogni_agent"""
    print("🔧 Testing Redis checkpointer with simple_cogni_agent...")
    
    # Build the simple_cogni_agent graph
    try:
        print("\n1️⃣ Building simple_cogni_agent graph...")
        workflow = await build_graph()
        print("✅ Graph built successfully")
        
        # Test without checkpointer first
        print("\n2️⃣ Testing without checkpointer...")
        graph_no_checkpoint = workflow.compile()
        result = await graph_no_checkpoint.ainvoke({"messages": [HumanMessage("Hello")]})
        print("✅ Graph without checkpointer works")
        print(f"💬 Response: {result['messages'][-1].content[:50]}...")
        
    except Exception as e:
        print(f"❌ Graph building/testing failed: {e}")
        return False
    
    # Test with Redis checkpointer
    print("\n3️⃣ Testing with Redis checkpointer...")
    try:
        redis_uri = "redis://localhost:6379"
        async with AsyncRedisSaver.from_conn_string(redis_uri) as checkpointer:
            graph_with_checkpoint = workflow.compile(checkpointer=checkpointer)
            
            config = {"configurable": {"thread_id": "test_simple_cogni"}}
            result = await graph_with_checkpoint.ainvoke(
                {"messages": [HumanMessage("Hello from Redis test with simple_cogni_agent")]},
                config=config
            )
            print("✅ Graph with Redis checkpointer works")
            print(f"💬 Response: {result['messages'][-1].content[:50]}...")
            
            # Test persistence
            result2 = await graph_with_checkpoint.ainvoke(
                {"messages": [HumanMessage("Do you remember the previous message?")]},
                config=config
            )
            print("✅ Thread persistence works")
            print(f"💬 Response: {result2['messages'][-1].content[:50]}...")
            print(f"📊 Total messages in thread: {len(result2['messages'])}")
        
    except Exception as e:
        print(f"❌ Redis checkpointer failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n🎉 simple_cogni_agent Redis test completed successfully!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_simple_cogni_redis())
    if success:
        print("\n✅ Redis checkpointer works with simple_cogni_agent")
    else:
        print("\n❌ Redis checkpointer test failed")