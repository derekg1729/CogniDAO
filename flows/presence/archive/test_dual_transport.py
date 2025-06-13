#!/usr/bin/env python3
"""
Test Script for AutoGen MCP Dual Transport
Simple validation before running full demonstration

Tests:
1. Math server can start and respond via stdio
2. AutoGen can connect to MCP tools
3. Basic tool execution works

Run this before the full demonstration to catch issues early
"""

import asyncio
import subprocess
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_math_server_direct():
    """Test math server directly via subprocess"""
    logger.info("🧮 Testing math server directly...")

    try:
        math_server_path = Path(__file__).parent / "math_server.py"

        if not math_server_path.exists():
            logger.error(f"❌ Math server not found: {math_server_path}")
            return False

        # Start math server process
        process = subprocess.Popen(
            ["python", str(math_server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Give it a moment to start
        time.sleep(1)

        # Check if process is running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            logger.error("❌ Math server failed to start")
            logger.error(f"STDOUT: {stdout}")
            logger.error(f"STDERR: {stderr}")
            return False

        logger.info("✅ Math server started successfully")

        # Terminate the test process
        process.terminate()
        process.wait()

        return True

    except Exception as e:
        logger.error(f"❌ Math server test failed: {e}")
        return False


async def test_mcp_imports():
    """Test that all required MCP imports work"""
    logger.info("📦 Testing MCP imports...")

    try:
        from autogen_ext.tools.mcp import StdioServerParams, SseServerParams
        # from autogen_ext.tools.mcp import mcp_server_tools
        from autogen_agentchat.agents import AssistantAgent
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        logger.info("✅ All MCP imports successful")
        logger.info(
            f"Available: {StdioServerParams.__name__}, {SseServerParams.__name__}, {AssistantAgent.__name__}, {OpenAIChatCompletionClient.__name__}"
        )
        return True

    except ImportError as e:
        logger.error(f"❌ MCP import failed: {e}")
        logger.error("Make sure autogen-ext[mcp] is installed")
        return False


async def test_openai_client():
    """Test OpenAI client can be created"""
    logger.info("🤖 Testing OpenAI client...")

    try:
        from autogen_ext.models.openai import OpenAIChatCompletionClient

        client = OpenAIChatCompletionClient(model="gpt-4o")
        logger.info(f"✅ OpenAI client created successfully: {client.__class__.__name__}")
        return True

    except Exception as e:
        logger.error(f"❌ OpenAI client test failed: {e}")
        logger.error("Check OPENAI_API_KEY environment variable")
        return False


async def test_basic_mcp_connection():
    """Test basic MCP connection to math server"""
    logger.info("🔌 Testing basic MCP connection...")

    try:
        from autogen_ext.tools.mcp import StdioServerParams, mcp_server_tools
        import os

        math_server_path = Path(__file__).parent / "math_server.py"

        server_params = StdioServerParams(
            command="python",
            args=[str(math_server_path)],
            env={**os.environ},
            read_timeout_seconds=10,
        )

        # This is the critical test - can we get tools without hanging?
        logger.info("🔍 Testing mcp_server_tools() call...")
        tools = await mcp_server_tools(server_params)

        logger.info(f"✅ MCP connection successful: {len(tools)} tools")
        logger.info(f"Tools: {[tool.name for tool in tools]}")

        # Verify we got the expected math tools
        expected_tools = {"add", "multiply", "subtract", "divide"}
        actual_tools = {tool.name for tool in tools}

        if expected_tools.issubset(actual_tools):
            logger.info("✅ All expected math tools found")
            return True
        else:
            logger.warning(f"⚠️ Missing tools: {expected_tools - actual_tools}")
            return False

    except Exception as e:
        logger.error(f"❌ MCP connection test failed: {e}")
        return False


async def run_all_tests():
    """Run all validation tests"""
    logger.info("🧪 Starting AutoGen MCP Dual Transport Validation Tests")
    logger.info("=" * 60)

    tests = [
        ("Math Server Direct", test_math_server_direct),
        ("MCP Imports", test_mcp_imports),
        ("OpenAI Client", test_openai_client),
        ("Basic MCP Connection", test_basic_mcp_connection),
    ]

    results = {}

    for test_name, test_func in tests:
        logger.info(f"\n📋 Running: {test_name}")
        try:
            result = await test_func()
            results[test_name] = result
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status}: {test_name}")
        except Exception as e:
            logger.error(f"❌ FAIL: {test_name} - {e}")
            results[test_name] = False

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 Test Results Summary:")

    passed = sum(results.values())
    total = len(results)

    for test_name, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"  {status} {test_name}")

    if passed == total:
        logger.info(f"\n🎉 ALL TESTS PASSED ({passed}/{total})")
        logger.info("🚀 Ready to run full demonstration!")
        return True
    else:
        logger.info(f"\n❌ TESTS FAILED ({passed}/{total})")
        logger.info("🔧 Fix issues before running demonstration")
        return False


if __name__ == "__main__":
    asyncio.run(run_all_tests())
