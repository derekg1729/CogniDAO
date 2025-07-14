"""
Simple test to verify the image generation graph works.
"""

import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.cogni_image_gen.graph import build_graph  # noqa: E402


def test_graph_creation():
    """Test that the graph can be created without errors and without event loop."""
    try:
        graph = build_graph()
        print("✅ Graph created successfully")
        print(f"Nodes: {list(graph.nodes.keys())}")
        print(f"Edges: {list(graph.edges)}")
        return True
    except Exception as e:
        print(f"❌ Graph creation failed: {e}")
        return False


def test_graph_structure():
    """Test that the graph has the expected structure."""
    try:
        graph = build_graph()
        
        # Check expected nodes (including human_checkpoint)
        expected_nodes = {"planner", "image_tool", "reviewer", "responder", "human_checkpoint"}
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


def main():
    """Run all tests."""
    print("🧪 Testing CogniDAO Image Generation Graph...")
    
    test_results = []
    
    # Test graph creation
    result1 = test_graph_creation()
    test_results.append(result1)
    
    # Test graph structure
    result2 = test_graph_structure()
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


def test_no_event_loop_required():
    """Test that graph building doesn't require an event loop."""
    try:
        # This should work without asyncio.run()
        build_graph()
        print("✅ Graph builds without event loop")
        return True
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            print(f"❌ Graph building requires event loop: {e}")
            return False
        else:
            print(f"❌ Unexpected error: {e}")
            return False
    except Exception as e:
        print(f"❌ Graph building failed: {e}")
        return False


if __name__ == "__main__":
    # Test without event loop first
    print("🧪 Testing graph building without event loop...")
    no_loop_result = test_no_event_loop_required()
    
    if no_loop_result:
        # Run other tests
        main_result = main()
        if not main_result:
            exit(1)
    else:
        print("❌ Event loop dependency test failed")
        exit(1)