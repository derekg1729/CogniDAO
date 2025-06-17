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

    print("🔍 Helicone observability enabled globally via proxy")
    print(f"   Base URL: {helicone_base_url}")
    print("   API Key: <redacted>")

    # Patch OpenAI when it gets imported
    def patch_openai():
        try:
            import openai

            if hasattr(openai, "OpenAI") and not hasattr(openai.OpenAI, "_helicone_patched"):
                original_init = openai.OpenAI.__init__

                def patched_init(self, *args, **kwargs):
                    # Set base_url to Helicone if not explicitly provided
                    if "base_url" not in kwargs:
                        kwargs["base_url"] = helicone_base_url

                    # Add Helicone auth header to default_headers
                    default_headers = kwargs.get("default_headers", {})
                    if "Helicone-Auth" not in default_headers:
                        default_headers["Helicone-Auth"] = f"Bearer {helicone_api_key}"
                        kwargs["default_headers"] = default_headers

                    # Call original constructor
                    return original_init(self, *args, **kwargs)

                openai.OpenAI.__init__ = patched_init
                openai.OpenAI._helicone_patched = True
                print("🔧 OpenAI client patched for Helicone integration")
        except ImportError:
            pass

    # Try to patch immediately if openai is already imported
    patch_openai()

    # Also set up a module finder to patch when openai gets imported later
    import sys
    import importlib.util

    class HeliconeModuleFinder:
        def find_spec(self, fullname, path, target=None):
            if fullname == "openai":
                # Let normal import happen
                spec = importlib.util.find_spec(fullname)
                if spec and spec.loader:
                    original_exec = spec.loader.exec_module

                    def patched_exec(module):
                        result = original_exec(module)
                        # Patch after module is loaded
                        if hasattr(module, "OpenAI") and not hasattr(
                            module.OpenAI, "_helicone_patched"
                        ):
                            original_init = module.OpenAI.__init__

                            def patched_init(self, *args, **kwargs):
                                if "base_url" not in kwargs:
                                    kwargs["base_url"] = helicone_base_url

                                default_headers = kwargs.get("default_headers", {})
                                if "Helicone-Auth" not in default_headers:
                                    default_headers["Helicone-Auth"] = f"Bearer {helicone_api_key}"
                                    kwargs["default_headers"] = default_headers

                                return original_init(self, *args, **kwargs)

                            module.OpenAI.__init__ = patched_init
                            module.OpenAI._helicone_patched = True
                            print("🔧 OpenAI client patched for Helicone integration")
                        return result

                    spec.loader.exec_module = patched_exec
                return spec
            return None

    # Install the module finder
    if not any(isinstance(finder, HeliconeModuleFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, HeliconeModuleFinder())

else:
    # No Helicone key - silent pass for development
    pass
