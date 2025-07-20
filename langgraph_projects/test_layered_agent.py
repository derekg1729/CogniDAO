#!/usr/bin/env python3
"""
Test script for the layered cogni agent.
"""

import asyncio
import sys
from pathlib import Path
from langchain_core.messages import HumanMessage

# Add src to path for absolute imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def test_layered_agent():
    """Test the layered cogni agent functionality."""
    try:
        from src.layered_cogni_agent.graph import build_compiled_graph
        
        print("🧪 Building and testing layered cogni agent...")
        graph = await build_compiled_graph()
        print(f"✅ Graph compiled successfully: {type(graph)}")
        
        # Test with a simple message
        print("\n🔵 Testing agent with simple message...")
        result = await graph.ainvoke({
            'messages': [HumanMessage(content='Hello! Can you introduce yourself and test your test_tool?')]
        })
        
        print("✅ Agent execution completed")
        print(f"📊 Messages returned: {len(result.get('messages', []))}")
        
        if result.get('messages'):
            last_msg = result['messages'][-1]
            print(f"📝 Last message type: {type(last_msg).__name__}")
            if hasattr(last_msg, 'content'):
                content = str(last_msg.content)
                print("💬 Response:")
                print("=" * 50)
                print(content)
                print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_layered_agent())
    sys.exit(0 if success else 1)