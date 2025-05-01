#!/usr/bin/env python
"""
Example: Using OllamaModelHandler with GitCogni

This script demonstrates how to use the OllamaModelHandler with GitCogni
to review a PR using a local model from Ollama instead of OpenAI API.
"""

import sys
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

# Import after sys.path adjustment
from experiments.src.core.models.ollama_model_handler import OllamaModelHandler  # noqa: E402


def setup_logging():
    """Setup basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("ollama_example")


def main():
    """
    Main example function to demonstrate OllamaModelHandler
    """
    logger = setup_logging()
    logger.info("Starting Ollama model handler example")

    # Create Ollama model handler
    logger.info("Creating OllamaModelHandler")
    model = OllamaModelHandler(
        default_model="deepseek-coder",  # Change this to match your available Ollama model
        api_url="http://localhost:11434/api",
    )

    # Test a simple completion
    logger.info("Testing a simple completion")
    system_message = "You are a helpful assistant who specializes in Python code."
    user_prompt = "Write a Python function to calculate the fibonacci sequence."

    try:
        response = model.create_chat_completion(
            system_message=system_message, user_prompt=user_prompt, temperature=0.7
        )

        content = model.extract_content(response)
        logger.info(f"Response received, content length: {len(content)}")
        print("\n----- MODEL RESPONSE -----")
        print(content)
        print("--------------------------\n")

    except Exception as e:
        logger.error(f"Error calling Ollama: {e}")
        # Note: Make sure Ollama server is running with:
        # ollama serve
        # And that you have the model pulled:
        # ollama pull deepseek-coder
        print("\nDid you start Ollama with 'ollama serve'?")
        print("Did you pull the deepseek-coder model with 'ollama pull deepseek-coder'?")
        return

    logger.info("Example completed successfully")


if __name__ == "__main__":
    main()
