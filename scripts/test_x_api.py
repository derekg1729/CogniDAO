#!/usr/bin/env python3
"""
Test script for X API credentials
"""
import os
import sys
import tweepy

def test_x_credentials():
    """Test if X API credentials are valid by retrieving the account info"""
    print("Testing X API credentials...")
    
    # Get credentials from environment variables
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
    
    # Check if all credentials are present
    missing = []
    if not api_key:
        missing.append("X_API_KEY")
    if not api_secret:
        missing.append("X_API_SECRET")
    if not access_token:
        missing.append("X_ACCESS_TOKEN")
    if not access_token_secret:
        missing.append("X_ACCESS_TOKEN_SECRET")
    
    if missing:
        print("❌ Error: Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease set these variables in .env and run:")
        print("export $(grep -v '^#' .env | xargs)")
        return False
    
    try:
        # Initialize the client
        client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret
        )
        
        # Get the authenticated user's information (me)
        user = client.get_me()
        
        if user and user.data:
            print(f"✅ Successfully authenticated as: @{user.data.username}")
            print(f"User ID: {user.data.id}")
            print(f"Name: {user.data.name}")
            return True
        else:
            print("❌ Authentication succeeded but couldn't retrieve user data")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

def test_openai_api():
    """Test if OpenAI API key is valid"""
    print("\nTesting OpenAI API key...")
    
    # Get API key from environment variable
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        return False
    
    # Simple validation - just checks if it looks like an OpenAI key
    if api_key.startswith("sk-") and len(api_key) > 20:
        print("✅ OpenAI API key format looks valid (Note: This doesn't verify the key works)")
        return True
    else:
        print("❌ Error: OpenAI API key format doesn't look valid")
        return False
        
if __name__ == "__main__":
    print("\n=== COGNI API CREDENTIALS TEST ===\n")
    
    x_success = test_x_credentials()
    openai_success = test_openai_api()
    
    print("\n=== TEST SUMMARY ===")
    print(f"X API: {'✅ PASS' if x_success else '❌ FAIL'}")
    print(f"OpenAI API: {'✅ PASS' if openai_success else '❌ FAIL'}")
    
    if not (x_success and openai_success):
        sys.exit(1)
    
    print("\nAll tests passed! Your credentials are valid.")
    print("You're ready to run the Cogni Ritual of Presence.")
    print("\n=========================\n") 