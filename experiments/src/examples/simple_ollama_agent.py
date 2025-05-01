#!/usr/bin/env python
"""
Example: A simple agent using the OllamaModelHandler

This script demonstrates a minimal agent pattern using the OllamaModelHandler
for local LLM inference with Ollama server.
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

# Import after sys.path adjustment
from experiments.src.core.models.ollama_model_handler import OllamaModelHandler  # noqa: E402


class SimpleCogniAgent:
    """
    A minimal agent that uses OllamaModelHandler for inference.

    This agent maintains conversation history and can process
    follow-up questions with context.
    """

    def __init__(
        self, model_handler: OllamaModelHandler, system_prompt: str = "You are a helpful assistant."
    ):
        """
        Initialize the agent with a model handler and system prompt.

        Args:
            model_handler: The model handler to use for generating responses
            system_prompt: The system prompt providing instructions to the model
        """
        self.model = model_handler
        self.system_prompt = system_prompt
        self.conversation_history: List[Dict[str, str]] = []
        self.logger = logging.getLogger("simple_agent")

    def ask(self, user_input: str) -> str:
        """
        Process a user query and generate a response.

        Args:
            user_input: The user's question or request

        Returns:
            The agent's response
        """
        self.logger.info(f"Received user input: {user_input}")

        try:
            # Get completion from model
            response_obj = self.model.create_chat_completion(
                system_message=self.system_prompt,
                user_prompt=user_input,
                message_history=self.conversation_history,
                temperature=0.7,
            )

            # Extract content
            response = self.model.extract_content(response_obj)

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "assistant", "content": response})

            self.logger.info(f"Generated response of length {len(response)}")
            return response

        except Exception as e:
            self.logger.error(f"Error during model inference: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

    def reset_conversation(self):
        """Clear the conversation history."""
        self.conversation_history = []
        self.logger.info("Conversation history cleared")


def setup_logging():
    """Setup basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("ollama_agent_example")


def main():
    """
    Main function to run the example
    """
    logger = setup_logging()
    logger.info("Starting simple Ollama agent example")

    # Initialize the model handler for Ollama
    model = OllamaModelHandler(default_model="deepseek-coder", api_url="http://localhost:11434/api")

    # Create our simple agent
    agent = SimpleCogniAgent(
        model_handler=model,
        system_prompt="You are part of a proof of concept. Respond with a variation of 'Hello, world!'",
    )

    # Test with a series of questions
    questions = [
        "Hello?",
        "Cogni, are you there?",
    ]

    # Run the conversation
    for i, question in enumerate(questions):
        logger.info(f"Question {i + 1}: {question}")

        response = agent.ask(question)

        logger.info(f"Response {i + 1}:")
        print("\n----- MODEL RESPONSE -----")
        print(response)
        print("--------------------------\n")

    logger.info("Example completed")


if __name__ == "__main__":
    main()
