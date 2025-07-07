#!/usr/bin/env python
"""
Test script to verify GitHub authentication is working
"""

import os
from github import Github, Auth

# Try to load .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
    print("✅ Loaded .env file using python-dotenv")
except ImportError:
    # Manual .env loading fallback
    print("📝 Loading .env file manually...")
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.strip().split("=", 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key] = value
        print("✅ Loaded .env file manually")
    else:
        print("⚠️ No .env file found")


def test_github_auth():
    """Test GitHub authentication and rate limiting"""
    print("\nTesting GitHub API authentication...")

    # Check for token
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        print(f"✅ Found GITHUB_TOKEN: {github_token[:8]}...")
        client = Github(auth=Auth.Token(github_token))
    else:
        print("⚠️  No GITHUB_TOKEN found, using anonymous client")
        client = Github()

    # Test API call and check rate limits
    try:
        # Get rate limit info
        rate_limit = client.get_rate_limit()
        core_limit = rate_limit.core

        print("\n📊 Rate Limit Status:")
        print(f"   Limit: {core_limit.limit} requests/hour")
        print(f"   Remaining: {core_limit.remaining}")
        print(f"   Reset time: {core_limit.reset}")

        # Test a simple API call
        user = client.get_user()
        if github_token:
            print(f"✅ Authenticated as: {user.login}")
        else:
            print("✅ Anonymous access working")

        # Determine if we have good rate limits
        if core_limit.limit >= 5000:
            print("🎉 Excellent! You have authenticated rate limits (5,000/hour)")
        elif core_limit.limit == 60:
            print("⚠️  You're using anonymous rate limits (60/hour)")
            print("   Consider adding GITHUB_TOKEN for much higher limits")

        return True

    except Exception as e:
        print(f"❌ Error testing GitHub API: {e}")
        return False


if __name__ == "__main__":
    test_github_auth()
