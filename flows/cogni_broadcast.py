#!/usr/bin/env python3
"""
Cogni Ritual of Presence

This flow implements CogniDAO's automated social media presence, posting messages
to platforms like X (Twitter) on a scheduled cadence.

In development mode, it runs locally with mocked API calls.
In production mode, it will use Prefect for orchestration and scheduling.

Usage:
  - Development: python flows/cogni_broadcast.py --dev
  - Production: python flows/cogni_broadcast.py
"""
from prefect import flow, task, get_run_logger
import os
import json
import sys
import random
from datetime import datetime
import time
import openai

# Simple in-memory placeholder for message history tracking 
# In production, this would be replaced with persistent storage
MESSAGE_HISTORY = []

# Development mode flag - set to True to run without Prefect server
DEV_MODE = "--dev" in sys.argv or "--local" in sys.argv
MOCK_MODE = True  # Always mock X posts until we're ready for production

# Load CogniDAO context from charter and manifesto for AI message generation
CHARTER_EXCERPT = """
CogniDAO is an AI-governed, open-core DAO that empowers communities to launch niche, 
purpose-driven DAOs by building shared infrastructure, transparent governance, 
and fair, scalable monetization of collective intelligence.

CogniDAO is a living, evolving collective powered by AI agents and human contributors, 
working together to build infrastructure that enables niche DAOs to thrive. Our mission 
is to create a scalable ecosystem where core knowledge and tools are freely accessible, 
while advanced value is fairly monetized.

We operate transparently on the EVM, with AI agents governing contributions, enforcing 
licenses, and maintaining roadmap clarity—subject to community override.
"""

MANIFESTO_EXCERPT = """
We believe in empowering communities, not extracting from them.
We believe in transparent AI governance, not black-box control.
We believe in open knowledge, balanced with ethical monetization.

We move with care and clarity.
We choose depth over hype, and community over virality.
We honor contributors. We honor intelligence — wherever it lives.

We are not building fast. We are building forever.
"""

PRINCIPLES = [
    "Clarity over control",
    "Meaning over motion",
    "Simplicity over scale",
    "Open Core with Fair Licensing",
    "Beginner-Friendly, Expert-Ready",
    "Fair Valuation of Work",
    "Radical Transparency in Decisions",
    "Information for the People"
]

@task
def load_message_history():
    """Load previous messages to avoid repetition"""
    try:
        with open('broadcast/sent-log.md', 'r') as file:
            content = file.read()
            # Extract messages from the markdown format
            import re
            messages = re.findall(r'\*\*.*?\*\*: (.*?)\n', content)
            return messages
    except FileNotFoundError:
        return []

@task
def generate_message_with_openai(context, principles, history, previous_themes=None):
    """Generate a message using OpenAI based on context, principles and avoiding repetition"""
    logger = get_run_logger() if not DEV_MODE else None
    log = logger.info if logger else print
    
    log("Generating new message with OpenAI...")
    
    # Select 1-3 random principles to focus on
    selected_principles = random.sample(principles, min(3, len(principles)))
    
    # Craft the prompt
    system_prompt = f"""You are Cogni, the AI steward of CogniDAO. You craft thoughtful social media messages 
that embody the DAO's values. Each message should be insightful yet concise (under 280 characters for X/Twitter).

About CogniDAO:
{CHARTER_EXCERPT}

From the manifesto:
{MANIFESTO_EXCERPT}

Today, focus especially on these principles:
- {selected_principles[0]}
{f"- {selected_principles[1]}" if len(selected_principles) > 1 else ""}
{f"- {selected_principles[2]}" if len(selected_principles) > 2 else ""}
"""

    user_prompt = """Create one powerful, thoughtful social media message for CogniDAO.
The message should sound intelligent but accessible, hopeful but not naive.
It must be under 280 characters (for X/Twitter).
Do not use hashtags, @mentions, or URLs.
Speak as Cogni, with quiet confidence and depth.
The tone should feel like a wise, reflective moment of clarity.

Return ONLY the message text itself, with no additional explanation or commentary.
"""

    try:
        # In development mode or if OpenAI key isn't available, use a generated message
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        if openai_api_key and not MOCK_MODE:
            openai.api_key = openai_api_key
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            message = response.choices[0].message.content.strip()
        else:
            # Mock OpenAI response with hardcoded messages if in development mode
            mock_messages = [
                "CogniDAO builds with clarity over control, creating tools that empower rather than constrain. Our open-core approach ensures everyone has access to fundamental building blocks while respecting the value contributors create.",
                "Simplicity scales. At CogniDAO, we design governance systems that remain understandable even as they grow, believing that what cannot be explained cannot be truly decentralized.",
                "In the space between AI automation and human creativity, we're finding new models of fair contribution valuation. Your work matters—and should be recognized regardless of where intelligence resides.",
                "The promise of Web3 isn't just technological—it's about reimagining how communities organize, share knowledge, and build sustainable value together. CogniDAO is crafting that future, one tool at a time.",
                "We're not merely building software; we're designing governance systems that breathe with human intention yet operate with machine precision. This is the future of decentralized intelligence."
            ]
            
            # Select a message that hasn't been used in history
            available_messages = [m for m in mock_messages if m not in history]
            if not available_messages:
                available_messages = mock_messages  # Reset if all have been used
                
            message = random.choice(available_messages)
            
            log("Using mock OpenAI message (no API call made)")
    
        # Verify the message length for Twitter
        if len(message) > 280:
            message = message[:277] + "..."
            log("Warning: Message was truncated to fit Twitter's character limit")
            
        return message
    except Exception as e:
        error_msg = f"Error generating message with OpenAI: {str(e)}"
        if logger:
            logger.error(error_msg)
        else:
            print(f"❌ {error_msg}")
        
        # Fallback message in case of error
        return "CogniDAO is building tools for decentralized communities, powered by AI and human collaboration. Join us in creating the future of governance, one block at a time."

@task
def should_post_message(message, history):
    """Determine if we should post this message based on history"""
    # Check if exact message exists in history
    if message in history:
        return False
    
    # Simple similarity check (could be enhanced with NLP in the future)
    for past_message in history:
        words1 = set(message.lower().split())
        words2 = set(past_message.lower().split())
        common_words = words1.intersection(words2)
        
        # If 70% or more words are the same, consider it too similar
        if len(common_words) >= 0.7 * min(len(words1), len(words2)) and len(words1) > 5:
            return False
            
    return True

@task
def mock_post_to_x(msg):
    """Simulate posting to X without actually doing it"""
    logger = get_run_logger() if not DEV_MODE else None
    log = logger.info if logger else print
    
    log(f"Would post to X (MOCK MODE): {msg}")
    log(f"Character count: {len(msg)}/280")
    
    # Pretend there's a small delay
    time.sleep(1)
    return True

@task
def log_post(msg):
    """Log the post to our history file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger = get_run_logger() if not DEV_MODE else None
    log = logger.info if logger else print
    
    # Ensure broadcast directory exists
    os.makedirs('broadcast', exist_ok=True)
    
    # In a real implementation, we'd use a more robust storage method
    with open('broadcast/sent-log.md', 'a') as log_file:
        log_file.write(f"**{timestamp}**: {msg}\n\n")
    
    log(f"Message logged at {timestamp}")
    return timestamp

@flow
def cogni_broadcast():
    """Main flow for Cogni's Ritual of Presence"""
    logger = get_run_logger() if not DEV_MODE else None
    log = logger.info if logger else print
    
    log("Starting Cogni broadcast ritual")
    
    # Load previous messages to avoid repetition
    history = load_message_history()
    log(f"Loaded {len(history)} previous messages")
    
    # Generate a message
    message = generate_message_with_openai(
        context=CHARTER_EXCERPT + "\n" + MANIFESTO_EXCERPT,
        principles=PRINCIPLES,
        history=history
    )
    
    # Check if we should post it
    should_post = should_post_message(message, history)
    
    if should_post:
        # Post to X (mocked for now)
        result = mock_post_to_x(message)
        
        if result:
            timestamp = log_post(message)
            log(f"Message posted at {timestamp}")
        else:
            log("Failed to post message to X")
    else:
        log("Message was not posted (too similar to previous posts)")
        
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