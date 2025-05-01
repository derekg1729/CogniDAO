#!/usr/bin/env python
"""
Example: A simple agent using the OllamaModelHandler

This script demonstrates a minimal agent pattern using the OllamaModelHandler
for local LLM inference with Ollama server.
"""

import sys
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

# Import the base CogniAgent
from infra_core.cogni_agents.base import CogniAgent  # noqa: E402

# Import memory bank for agent initialization
from infra_core.memory.memory_bank import CogniMemoryBank  # noqa: E402

# Import OllamaModelHandler from its new location
from infra_core.model_handlers.ollama_handler import OllamaModelHandler  # noqa: E402


class SimpleCogniAgent(CogniAgent):
    """
    A minimal agent that uses OllamaModelHandler for inference.

    Inherits from CogniAgent base class and implements the required
    abstract methods while maintaining conversation history.
    """

    def __init__(
        self,
        model_handler: OllamaModelHandler,
        system_prompt: str = "You are a helpful assistant.",
        agent_root: Optional[Path] = None,
        name: str = "simple-ollama-agent",
    ):
        """
        Initialize the agent with a model handler and system prompt.

        Args:
            model_handler: The model handler to use for generating responses
            system_prompt: The system prompt providing instructions to the model
            agent_root: Root directory for agent outputs (optional)
            name: Name of the agent instance
        """
        # Set up memory bank for agent
        memory_root = Path("./data/memory_banks/experiments")
        memory_root.mkdir(exist_ok=True, parents=True)
        # Generate a session ID using timestamp
        session_id = f"simple_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        memory = CogniMemoryBank(
            memory_bank_root=memory_root,
            project_name="simple_agent",
            session_id=session_id,  # Use generated session ID string
        )

        # Set up default paths if needed
        if agent_root is None:
            agent_root = Path("./data/agent_outputs/simple_agent")
            agent_root.mkdir(exist_ok=True, parents=True)

        # Call parent initializer
        super().__init__(
            name=name,
            spirit_path=Path(
                "infra_core/cogni_spirit/spirits/cogni-core-spirit.md"
            ),  # Default spirit
            agent_root=agent_root,
            memory=memory,
            model=model_handler,  # Pass model handler to base class
        )

        # Store additional properties
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

        # Prepare input for the act method
        prepared_input = self.prepare_input(query=user_input)

        # Process through the act method
        result = self.act(prepared_input)

        # Return the response from the result
        return result.get("response", "No response generated")

    def prepare_input(self, query: str) -> Dict[str, Any]:
        """
        Prepare input data for the act method.

        Args:
            query: The user query

        Returns:
            Dictionary with prepared input data
        """
        return {
            "query": query,
            "system_prompt": self.system_prompt,
            "conversation_history": self.conversation_history,
        }

    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the input and generate a response.

        Args:
            prepared_input: Dictionary with query and other data

        Returns:
            Dictionary with response and other data
        """
        query = prepared_input.get("query", "")
        system_prompt = prepared_input.get("system_prompt", self.system_prompt)
        conversation_history = prepared_input.get("conversation_history", self.conversation_history)

        try:
            # Get completion from model using the model handler from base class
            response_obj = self.model.create_chat_completion(
                system_message=system_prompt,
                user_prompt=query,
                message_history=conversation_history,
                temperature=0.7,
            )

            # Extract content
            response = self.model.extract_content(response_obj)

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": response})

            self.logger.info(f"Generated response of length {len(response)}")

            # Prepare the result
            result = {
                "query": query,
                "response": response,
                "timestamp": datetime.now().isoformat(),
                "conversation_length": len(self.conversation_history)
                // 2,  # Count turns, not messages
            }

            # Record the action in memory
            self.record_action(result)

            return result

        except Exception as e:
            self.logger.error(f"Error during model inference: {e}")
            error_response = f"Sorry, I encountered an error: {str(e)}"

            # Return error result
            return {
                "query": query,
                "response": error_response,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def reset_conversation(self):
        """Clear the conversation history."""
        self.conversation_history = []
        self.logger.info("Conversation history cleared")

    def format_output_markdown(self, data: Dict[str, Any]) -> str:
        """
        Format output data as Markdown.

        Args:
            data: Dictionary of output data

        Returns:
            Formatted markdown string
        """
        lines = [f"# {self.name} Output"]
        lines.append("")

        # Add query and response
        if "query" in data:
            lines.append(f"## Query\n\n{data['query']}")

        if "response" in data:
            lines.append(f"## Response\n\n{data['response']}")

        # Add any other data
        for key, value in data.items():
            if key not in ["query", "response"]:
                if isinstance(value, (dict, list)):
                    # Convert complex objects to formatted JSON
                    lines.append(f"## {key}\n\n```json\n{json.dumps(value, indent=2)}\n```")
                else:
                    lines.append(f"## {key}\n\n{value}")

        return "\n\n".join(lines)


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
