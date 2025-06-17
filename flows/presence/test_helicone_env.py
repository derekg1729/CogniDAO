#!/usr/bin/env python3
"""
Simple test script to verify Helicone environment setup for AI flows.
Run this before executing AI education team flow to ensure Helicone will receive data.
"""

import os
import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import UserMessage


async def test_helicone_setup():
    """Test if Helicone is properly configured and receiving data."""
    print("🔍 Checking Helicone environment setup...")

    # Check environment variables
    helicone_api_key = os.getenv("HELICONE_API_KEY", "").strip()
    helicone_base_url = os.getenv("HELICONE_BASE_URL", "https://oai.helicone.ai/v1").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()

    print("📋 Environment Variables:")
    print(f"   HELICONE_API_KEY: {'✅ Set' if helicone_api_key else '❌ Not set'}")
    print(f"   HELICONE_BASE_URL: {helicone_base_url}")
    print(f"   OPENAI_API_KEY: {'✅ Set' if openai_api_key else '❌ Not set'}")

    if not helicone_api_key:
        print("\n❌ HELICONE_API_KEY not set. Helicone observability will NOT work.")
        print("💡 Set HELICONE_API_KEY=sk-helicone-36t5xkq-n5belea-x3zrnia-7wglpva to enable")
        return False

    if not openai_api_key:
        print("\n❌ OPENAI_API_KEY not set. API calls will fail.")
        return False

    print("\n✅ Environment variables properly configured!")

    # Test actual API call
    print("\n🧪 Testing actual API call with Helicone...")

    try:
        model_client = OpenAIChatCompletionClient(
            model="gpt-4o-mini",  # Use cheaper model for testing
            base_url=helicone_base_url,
            default_headers={
                "Helicone-Auth": f"Bearer {helicone_api_key}",
                "Helicone-Session-Id": "test-helicone-setup",
                "Helicone-Property-Test": "environment-verification",
                "Helicone-Property-Flow": "test-setup",
            },
        )

        response = await model_client.create(
            [
                UserMessage(
                    content="Hello! This is a test message to verify Helicone integration. Please respond with 'Helicone test successful!'",
                    source="user",
                )
            ]
        )

        print("🎉 API call successful!")
        print(f"📝 Response: {response.content}")
        print(f"📊 Usage: {response.usage}")
        print(
            "\n✅ If Helicone is working, you should see this request in your Helicone dashboard!"
        )
        print("🌐 Check: https://www.helicone.ai/requests")

        await model_client.close()
        return True

    except Exception as e:
        print(f"❌ API call failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_helicone_setup())
    if success:
        print("\n🎯 Environment is ready for Helicone observability!")
    else:
        print("\n⚠️  Fix the issues above before running AI flows.")
