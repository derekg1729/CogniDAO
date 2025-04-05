#!/usr/bin/env python3
"""
Cogni Ritual of Presence

This flow implements CogniDAO's automated social media presence, posting messages
to platforms like X (Twitter) on a scheduled cadence.

In production mode, it uses Prefect for orchestration and scheduling.
In development mode, it can run locally without the Prefect server.

Usage:
  - Development: python flows/cogni_broadcast.py
  - Production: Deploy with `prefect deployment build flows/cogni_broadcast.py:cogni_broadcast -n "Cogni Ritual of Presence" --cron "0 10 * * 2,5" -a`
"""
from prefect import flow, task, get_run_logger
import os
from datetime import datetime
import sys

# Simple in-memory placeholder for message history tracking 
# In production, this would be replaced with a Prefect artifact or database
MESSAGE_HISTORY = []

# Context from charter and manifesto to inform AI generation
COGNI_CONTEXT = """
CogniDAO exists to empower decentralized niche communities through shared infrastructure, 
AI-powered governance, and open knowledge.

Our core principles include:
- Clarity over control
- Meaning over motion
- Simplicity over scale
- Open Core with Fair Licensing
- Beginner-Friendly, Expert-Ready
- Fair Valuation of Work
- Radical Transparency in Decisions

We move with care and clarity, choosing depth over hype, and community over virality.
"""

# Development mode flag - set to True to run without Prefect server
DEV_MODE = "--dev" in sys.argv

@task
def generate_message(context, history):
    """Generate a new message using context and previous messages"""
    logger = get_run_logger() if not DEV_MODE else None
    
    if logger:
        logger.info("Generating new message with AI...")
    else:
        print("Generating new message with AI...")
    
    # Placeholder AI message - replace with actual OpenAI call when ready
    message = "CogniDAO is built on principles of clarity, openness, and fair governance. Join us in building the future of decentralized communities."
    
    # Log that we would use OpenAI in production
    if logger:
        logger.info("In production, this would use OpenAI with context and history")
    else:
        print("In production, this would use OpenAI with context and history")
    
    return message

@task
def should_post_message(message, history):
    """Determine if we should post this message based on history"""
    # Simple logic - don't post if the exact message is in history
    return message not in history

@task
def mock_post_to_x(msg):
    """Simulate posting to X without actually doing it"""
    logger = get_run_logger() if not DEV_MODE else None
    
    if logger:
        logger.info(f"MOCK TWEET: {msg}")
    else:
        print(f"MOCK TWEET: {msg}")
    
    return True

@task
def log_post(msg):
    """Log the post to our history file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger = get_run_logger() if not DEV_MODE else None
    
    # In a real implementation, we'd use a more robust storage method
    with open('broadcast/sent-log.md', 'a') as log_file:
        log_file.write(f"**{timestamp}**: {msg}\n\n")
    
    # Add to our in-memory history
    MESSAGE_HISTORY.append(msg)
    
    if logger:
        logger.info(f"Message logged at {timestamp}")
    else:
        print(f"Message logged at {timestamp}")
    
    return timestamp

@flow
def cogni_broadcast():
    """Main flow for Cogni's Ritual of Presence"""
    logger = get_run_logger() if not DEV_MODE else None
    
    if logger:
        logger.info("Starting Cogni broadcast ritual")
    else:
        print("Starting Cogni broadcast ritual")
    
    # Generate a message
    message = generate_message(COGNI_CONTEXT, MESSAGE_HISTORY)
    
    # Check if we should post it
    should_post = should_post_message(message, MESSAGE_HISTORY)
    
    if should_post:
        # In MVP, we just mock the posting
        mock_post_to_x(message)
        timestamp = log_post(message)
        
        if logger:
            logger.info(f"Message posted at {timestamp}")
        else:
            print(f"Message posted at {timestamp}")
    else:
        if logger:
            logger.info("Message was not posted (duplicate or invalid)")
        else:
            print("Message was not posted (duplicate or invalid)")
        
    return message

if __name__ == "__main__":
    if DEV_MODE:
        # Development mode - run without Prefect server
        print("\n=== COGNI RITUAL OF PRESENCE (DEV MODE) ===\n")
        result = cogni_broadcast()
        print(f"\nRitual completed successfully with message: {result}")
        print("\n=================================\n")
    else:
        # Production mode - use Prefect orchestration
        cogni_broadcast() 