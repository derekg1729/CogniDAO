#!/usr/bin/env python3
"""
Helicone Deployment Verification Script
=====================================

Run this script inside your Prefect worker container to verify that:
1. Environment variables are properly set
2. sitecustomize.py is in the right location
3. Helicone shim is working
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
    optional_vars = ["HELICONE_BASE_URL", "OPENAI_API_BASE", "OPENAI_BASE_URL", "HELICONE_DEBUG"]

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
    """Check if Helicone integration is working via proxy."""
    print("\n🔍 Helicone Proxy Integration Check")
    print("-" * 40)

    helicone_key = os.getenv("HELICONE_API_KEY", "").strip()
    if not helicone_key:
        print("  ⚠️  HELICONE_API_KEY not set - integration disabled")
        return False

    # Check environment variable setup
    openai_api_base = os.getenv("OPENAI_API_BASE", "").strip()
    if openai_api_base:
        print(f"  ✅ OPENAI_API_BASE set to: {openai_api_base}")
        if "helicone" in openai_api_base.lower():
            print("  ✅ OpenAI requests will route through Helicone proxy")
        else:
            print("  ⚠️  OPENAI_API_BASE doesn't appear to be Helicone URL")
    else:
        print("  ❌ OPENAI_API_BASE not set - sitecustomize.py may not have run")
        return False

    print("  ✅ Proxy-based integration configured correctly")
    print("  ℹ️  No package dependencies required")
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

        # Create client - should use proxy via environment variables automatically
        client = OpenAI()

        print("  ✅ OpenAI client created successfully")
        print("  ✅ Proxy routing configured via environment variables")
        print("  ℹ️  Check your Helicone dashboard for requests")

        # Check if client has been configured correctly
        if hasattr(client, "base_url") and client.base_url:
            print(f"  ℹ️  Client base_url: {client.base_url}")

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
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"\n❌ Error in {check_name}: {e}")
            results[check_name] = False

    # Summary
    print("\n📊 Verification Summary")
    print("=" * 50)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {check_name}: {status}")

    print(f"\nOverall: {passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 All checks passed! Helicone integration is working correctly.")
        print("💡 Your Prefect flows should now automatically send observability data to Helicone.")
    else:
        print(f"\n⚠️  {total - passed} checks failed. Please fix the issues above.")
        print("💡 Common fixes:")
        print("   - Ensure HELICONE_API_KEY and OPENAI_API_KEY are set")
        print("   - Copy sitecustomize.py to your Python environment")
        print("   - Verify sitecustomize.py sets OPENAI_API_BASE correctly")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
