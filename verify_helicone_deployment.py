#!/usr/bin/env python3
"""
Helicone Deployment Verification Script
=====================================

Run this script inside your Prefect worker container to verify that:
1. Environment variables are properly set
2. sitecustomize.py is in the right location
3. Helicone integration is working
4. AutoGen will use Helicone proxy

Usage:
  docker exec -it <prefect-worker-container> python /workspace/verify_helicone_deployment.py
"""

import os
import sys
import importlib.util


def check_environment():
    """Check if environment variables are properly set."""
    print("🔧 Environment Variables Check")
    print("-" * 40)

    required_vars = ["OPENAI_API_KEY", "HELICONE_API_KEY"]
    optional_vars = ["HELICONE_BASE_URL", "OPENAI_API_BASE", "OPENAI_BASE_URL"]

    env_status = {}

    for var in required_vars:
        value = os.getenv(var, "").strip()
        env_status[var] = bool(value)
        status = "✅ Set" if value else "❌ Missing"
        display_value = "<redacted>" if value and "KEY" in var else (value or "Not set")
        print(f"  {var}: {status} ({display_value})")

    for var in optional_vars:
        value = os.getenv(var, "").strip()
        env_status[var] = bool(value)
        status = "✅ Set" if value else "ℹ️  Default"
        print(f"  {var}: {status} ({value or 'Not set'})")

    return env_status


def check_sitecustomize():
    """Check if sitecustomize.py is properly installed."""
    print("\n📁 sitecustomize.py Installation Check")
    print("-" * 40)

    # Check if sitecustomize.py exists in site-packages
    site_packages_paths = [
        "/usr/local/lib/python3.12/site-packages/sitecustomize.py",
        "/usr/lib/python3.12/site-packages/sitecustomize.py",
    ]

    sitecustomize_found = False
    for path in site_packages_paths:
        if os.path.exists(path):
            print(f"  ✅ Found sitecustomize.py at: {path}")
            sitecustomize_found = True
            break

    if not sitecustomize_found:
        print("  ❌ sitecustomize.py not found in expected locations:")
        for path in site_packages_paths:
            print(f"     {path}")

        # Check if it's in Python path
        for path in sys.path:
            sitecustomize_path = os.path.join(path, "sitecustomize.py")
            if os.path.exists(sitecustomize_path):
                print(f"  ℹ️  Found sitecustomize.py in Python path: {sitecustomize_path}")
                sitecustomize_found = True
                break

    # Check if sitecustomize module was imported
    if "sitecustomize" in sys.modules:
        print("  ✅ sitecustomize module was automatically imported")
    else:
        print("  ❌ sitecustomize module was not imported")

    return sitecustomize_found


def check_helicone_integration():
    """Check if Helicone integration is working."""
    print("\n🔍 Helicone Integration Check")
    print("-" * 40)

    helicone_key = os.getenv("HELICONE_API_KEY", "").strip()
    openai_api_base = os.getenv("OPENAI_API_BASE", "").strip()

    if not helicone_key:
        print("  ⚠️  HELICONE_API_KEY not set - integration disabled")
        return False

    if openai_api_base:
        print(f"  ✅ OPENAI_API_BASE set to: {openai_api_base}")
        if "helicone" in openai_api_base.lower():
            print("  ✅ OpenAI requests will route through Helicone")
        else:
            print("  ⚠️  OPENAI_API_BASE doesn't appear to be Helicone URL")
    else:
        print("  ❌ OPENAI_API_BASE not set - sitecustomize.py may not have run")
        return False

    # Check OpenAI module state
    try:
        import openai

        print("  ✅ OpenAI module imported successfully")

        if hasattr(openai, "base_url") and openai.base_url:
            print(f"  ✅ openai.base_url set to: {openai.base_url}")
        else:
            print("  ℹ️  openai.base_url not set (may use environment variables)")
    except ImportError as e:
        print(f"  ❌ Failed to import OpenAI: {e}")
        return False

    return True


def check_autogen_compatibility():
    """Check if AutoGen will work with Helicone."""
    print("\n🤖 AutoGen Compatibility Check")
    print("-" * 40)

    try:
        # Check if AutoGen is available
        autogen_spec = importlib.util.find_spec("autogen_ext.models.openai")
        if autogen_spec is None:
            print("  ℹ️  AutoGen not installed - skipping compatibility check")
            return True

        print("  ✅ AutoGen is available")

        # Check environment variables that AutoGen respects
        openai_api_base = os.getenv("OPENAI_API_BASE", "").strip()
        openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()

        if openai_api_base or openai_base_url:
            print("  ✅ AutoGen will use Helicone proxy via environment variables")
            print(f"     OPENAI_API_BASE: {openai_api_base or 'Not set'}")
            print(f"     OPENAI_BASE_URL: {openai_base_url or 'Not set'}")
        else:
            print("  ❌ AutoGen may not use Helicone proxy - environment variables not set")
            return False

    except Exception as e:
        print(f"  ⚠️  Error checking AutoGen compatibility: {e}")
        return False

    return True


def run_simple_test():
    """Run a simple test to verify the setup."""
    print("\n🧪 Simple Integration Test")
    print("-" * 40)

    helicone_key = os.getenv("HELICONE_API_KEY", "").strip()
    if not helicone_key:
        print("  ⚠️  Skipping test - HELICONE_API_KEY not set")
        return False

    try:
        from openai import OpenAI

        # Create client - should use environment variables automatically
        client = OpenAI()

        print("  ✅ OpenAI client created successfully")
        print("  ℹ️  Client should automatically route through Helicone")
        print("  ℹ️  Check your Helicone dashboard for requests")

        # Use client to avoid unused variable warning
        _ = client.api_key is not None

        return True

    except Exception as e:
        print(f"  ❌ Failed to create OpenAI client: {e}")
        return False


def main():
    """Run all verification checks."""
    print("🔍 Helicone Deployment Verification")
    print("=" * 50)

    checks = [
        ("Environment Variables", check_environment),
        ("sitecustomize.py Installation", check_sitecustomize),
        ("Helicone Integration", check_helicone_integration),
        ("AutoGen Compatibility", check_autogen_compatibility),
        ("Simple Integration Test", run_simple_test),
    ]

    results = {}
    for name, check_func in checks:
        try:
            result = check_func()
            results[name] = result
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results[name] = False

    # Summary
    print("\n" + "=" * 50)
    print("📋 Verification Summary")
    print("-" * 25)

    all_good = True
    for name, result in results.items():
        if isinstance(result, dict):
            # Environment check returns dict
            has_helicone = result.get("HELICONE_API_KEY", False)
            has_openai = result.get("OPENAI_API_KEY", False)
            status = "✅" if (has_helicone and has_openai) else "⚠️"
            print(f"  {status} {name}")
            if not (has_helicone and has_openai):
                all_good = False
        else:
            status = "✅" if result else "❌"
            print(f"  {status} {name}")
            if not result:
                all_good = False

    print("\n" + "=" * 50)
    if all_good:
        print("🎉 All checks passed! Helicone integration should be working.")
        print("   Run your AI Education Team flow and check the Helicone dashboard.")
    else:
        print("⚠️  Some checks failed. Review the issues above.")
        print("   You may need to rebuild the Docker container or check environment variables.")

    print("\n💡 To test with a real flow:")
    print("   1. Run your AI Education Team flow")
    print("   2. Check https://www.helicone.ai/requests for API calls")
    print("   3. Look for requests with your session/property tags")


if __name__ == "__main__":
    main()
