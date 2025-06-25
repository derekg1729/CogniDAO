#!/usr/bin/env python3
"""
Test Playwright Control Flow System
====================================

Simple test script to validate the Control Flow agent system works
with Playwright MCP. This can be run independently to test the setup.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add workspace to path
current_dir = Path(__file__).parent
workspace_root = current_dir.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

# Import the Control Flow system
from flows.examples.playwright_control_flow import playwright_control_flow  # noqa: E402


async def test_control_flow_system():
    """Test the Playwright Control Flow system with basic navigation"""
    print("🧪 Testing Playwright Control Flow System")
    print("=" * 50)

    # Set test environment variables
    os.environ["PLAYWRIGHT_MCP_SSE_URL"] = "http://toolhive:24162/sse"
    os.environ["NAVIGATION_OBJECTIVE"] = (
        "Navigate to httpbin.org/forms/post, fill out a simple form, "
        "and demonstrate basic web interaction capabilities"
    )

    print(f"🔗 Target URL: {os.environ['PLAYWRIGHT_MCP_SSE_URL']}")
    print(f"🎯 Mission: {os.environ['NAVIGATION_OBJECTIVE']}")
    print()

    try:
        # Run the Control Flow system
        result = await playwright_control_flow()

        print("📊 Test Results:")
        print(f"   Status: {result.get('status', 'unknown')}")

        if result.get("status") == "success":
            summary = result.get("summary", {})
            print(f"   Tools Available: {summary.get('tools_available', 0)}")
            print(f"   Agents Created: {summary.get('agents_created', 0)}")
            print(f"   Mission Success: {summary.get('mission_success', False)}")

            architecture = result.get("architecture_info", {})
            print(f"   Architecture: {architecture.get('type', 'unknown')}")
            print(f"   Template Type: {architecture.get('template_type', 'unknown')}")
            print(f"   Legacy Format: {architecture.get('legacy_format', True)}")

        else:
            print(f"   Error: {result.get('error', 'Unknown error')}")
            print(f"   Stage: {result.get('stage', 'unknown')}")

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()

    print("\n🏁 Test complete!")


if __name__ == "__main__":
    print("Starting Playwright Control Flow System Test...")
    asyncio.run(test_control_flow_system())
