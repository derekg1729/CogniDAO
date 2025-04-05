#!/usr/bin/env python3
"""
Script to set up Prefect secrets for CogniDAO
"""
import os
import sys
from prefect.blocks.system import Secret

def create_secret(name, value):
    """Create a Secret block with the given name and value"""
    print(f"Creating secret: {name}")
    secret_block = Secret(value=value)
    secret_block.save(name=name, overwrite=True)
    print(f"✅ Secret '{name}' created successfully")

def setup_secrets():
    """Set up all required secrets for CogniDAO"""
    secrets = {
        "x-api-key": os.environ.get("X_API_KEY", ""),
        "x-api-secret": os.environ.get("X_API_SECRET", ""),
        "x-access-token": os.environ.get("X_ACCESS_TOKEN", ""),
        "x-access-token-secret": os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
        "openai-api-key": os.environ.get("OPENAI_API_KEY", "")
    }
    
    # Check if required environment variables are set
    missing_vars = [key for key, value in secrets.items() if not value]
    
    if missing_vars:
        print("❌ Error: The following environment variables are not set:")
        for var in missing_vars:
            print(f"  - {var.upper()}")
        print("\nPlease set these variables in your environment and try again.")
        print("You can do this by creating a .env file and loading it before running this script:")
        print("\nexport $(grep -v '^#' .env | xargs)")
        sys.exit(1)
    
    # Create all secrets
    for name, value in secrets.items():
        create_secret(name, value)
    
    print("\n✨ All secrets created successfully! You can now use them in your flows.")
    print("\nAccess them with:")
    print("```python")
    print("from prefect.blocks.system import Secret")
    print("x_api_key = Secret.load('x-api-key').get()")
    print("```")

if __name__ == "__main__":
    print("Setting up Prefect secrets for CogniDAO...")
    setup_secrets() 