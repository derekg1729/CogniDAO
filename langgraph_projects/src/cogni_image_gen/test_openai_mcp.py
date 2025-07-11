"""
Test OpenAI MCP connection and tools.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.shared_utils.tool_registry import get_tools  # noqa: E402
from src.shared_utils import get_logger  # noqa: E402

logger = get_logger(__name__)


async def test_openai_mcp_connection():
    """Test OpenAI MCP server connection."""
    try:
        print("🔌 Testing OpenAI MCP connection...")
        tools = await get_tools("openai")
        
        if tools:
            print(f"✅ OpenAI MCP connection successful! Found {len(tools)} tools:")
            for tool in tools:
                print(f"  - {tool.name}: {tool.description}")
        else:
            print("❌ OpenAI MCP connection failed - no tools returned")
            return False
            
        # Look for expected OpenAI tools
        expected_tools = ["GenerateImage", "EditImage", "CreateImageVariation"]
        found_tools = [tool.name for tool in tools]
        
        missing_tools = [tool for tool in expected_tools if tool not in found_tools]
        if missing_tools:
            print(f"⚠️  Missing expected tools: {missing_tools}")
        
        available_expected = [tool for tool in expected_tools if tool in found_tools]
        if available_expected:
            print(f"✅ Found expected tools: {available_expected}")
        
        return True
        
    except Exception as e:
        print(f"❌ OpenAI MCP connection test failed: {e}")
        return False


async def main():
    """Run OpenAI MCP connection test."""
    print("🧪 Testing OpenAI MCP Connection...")
    
    success = await test_openai_mcp_connection()
    
    if success:
        print("\n🎉 OpenAI MCP connection test passed!")
    else:
        print("\n❌ OpenAI MCP connection test failed!")
        print("Make sure the OpenAI MCP server is deployed and accessible at:")
        print("  http://toolhive:24163/sse")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())