"""
Universal Helicone Integration via Environment Variables
======================================================

This module automatically configures OpenAI SDK libraries to route through Helicone
when environment variables are configured. Works for ANY library that uses OpenAI SDK:
- AutoGen
- LangChain
- LiteLLM
- Custom handlers
- Direct OpenAI usage

Environment Variables:
- HELICONE_API_KEY: Required for Helicone observability
- HELICONE_BASE_URL: Optional, defaults to "https://oai.helicone.ai/v1"
- OPENAI_API_BASE: Automatically set to HELICONE_BASE_URL when Helicone is enabled

Safety: If HELICONE_API_KEY is missing, this becomes a no-op.
"""

import os

# Check if Helicone should be enabled
helicone_api_key = os.getenv("HELICONE_API_KEY", "").strip()

if helicone_api_key:
    # Set default base URL if not provided
    helicone_base_url = os.getenv("HELICONE_BASE_URL", "https://oai.helicone.ai/v1").strip()

    # Set OpenAI base URL for libraries that respect this env var (like AutoGen)
    os.environ.setdefault("OPENAI_API_BASE", helicone_base_url)
    os.environ.setdefault("OPENAI_BASE_URL", helicone_base_url)  # For Instructor/BentoML

    # CRITICAL: Also set openai.base_url directly for libs that use the client attribute
    try:
        import openai

        openai.base_url = helicone_base_url
    except ImportError:
        pass  # OpenAI not yet imported, will be set when it is

    # Optional: Enable proxy-side caching if requested
    if os.getenv("HELICONE_LOG_CACHE", "").lower() in ("true", "1", "yes"):
        os.environ.setdefault("HELICONE_CACHE_ENABLED", "true")

    print("🔍 Helicone observability enabled globally via proxy")
    print(f"   Base URL: {helicone_base_url}")
    print("   API Key: <redacted>")
else:
    # No Helicone key - silent pass for development
    pass
