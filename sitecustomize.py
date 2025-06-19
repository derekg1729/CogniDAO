"""
Universal Helicone Integration via Proxy
=======================================

This module automatically configures OpenAI SDK libraries to route through Helicone
using environment variables. Works for ANY library that uses OpenAI SDK:
- AutoGen
- LangChain
- LiteLLM
- Custom handlers
- Direct OpenAI usage

Environment Variables:
- HELICONE_API_KEY: Required for Helicone observability
- HELICONE_BASE_URL: Optional, defaults to "https://oai.helicone.ai/v1"

Safety: If HELICONE_API_KEY is missing, this becomes a no-op.
"""

import os

# Check if Helicone should be enabled
helicone_api_key = os.getenv("HELICONE_API_KEY", "").strip()

if helicone_api_key:
    # Set OpenAI base URL for libraries that respect this env var
    helicone_base_url = os.getenv("HELICONE_BASE_URL", "https://oai.helicone.ai/v1").strip()
    os.environ.setdefault("OPENAI_API_BASE", helicone_base_url)
    os.environ.setdefault("OPENAI_BASE_URL", helicone_base_url)

    # Optional debug logging (can be disabled by setting HELICONE_DEBUG=false)
    if os.getenv("HELICONE_DEBUG", "true").lower() == "true":
        print("🔍 Helicone observability enabled via proxy")
        print(f"   Base URL: {helicone_base_url}")
        print("   Integration: Environment variables only (no package required)")
else:
    # No Helicone key - silent pass for development
    pass
