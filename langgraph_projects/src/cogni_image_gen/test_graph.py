"""
Simple test to verify the image generation graph works.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.cogni_image_gen.graph import build_graph  # noqa: E402


async def test_graph_creation():
    """Test that the graph can be created without errors."""
    try:
        graph = await build_graph()
        print("✅ Graph created successfully")
        print(f"Nodes: {list(graph.nodes.keys())}")
        print(f"Edges: {list(graph.edges)}")
        return True
    except Exception as e:
        print(f"❌ Graph creation failed: {e}")
        return False


async def test_graph_structure():
    """Test that the graph has the expected structure."""
    try:
        graph = await build_graph()
        
        # Check expected nodes
        expected_nodes = {"planner", "image_tool", "reviewer", "responder"}
        actual_nodes = set(graph.nodes.keys())
        
        if expected_nodes == actual_nodes:
            print("✅ Graph has expected nodes")
        else:
            print(f"❌ Node mismatch. Expected: {expected_nodes}, Got: {actual_nodes}")
            return False
        
        # Check that we have edges
        edges_count = len(list(graph.edges))
        if edges_count > 0:
            print(f"✅ Graph has {edges_count} edges")
        else:
            print("❌ Graph has no edges")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Graph structure test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🧪 Testing CogniDAO Image Generation Graph...")
    
    test_results = []
    
    # Test graph creation
    result1 = await test_graph_creation()
    test_results.append(result1)
    
    # Test graph structure
    result2 = await test_graph_structure()
    test_results.append(result2)
    
    # Summary
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    asyncio.run(main())