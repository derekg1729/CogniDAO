"""
Ollama Model Handler

Implementation of BaseModelHandler for communicating with Ollama server
using its REST API endpoints.

Moved from experiments/src/core/models to legacy_logseq/model_handlers
as part of consolidating model handler implementations.
"""

import json
import requests
import logging
from typing import Dict, Optional, Union, Any, List

from infra_core.model_handlers.base import BaseModelHandler


class OllamaModelHandler(BaseModelHandler):
    """
    Ollama model handler for local inference using headless Ollama server.

    Sends requests to a local Ollama server running DeepSeek, Mistral or other models.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:11434/api",
        default_model: str = "deepseek-coder",
        timeout: int = 120,
    ):
        """
        Initialize Ollama model handler.

        Args:
            api_url: Base URL for Ollama API (default: http://localhost:11434/api)
            default_model: Default model name to use with Ollama
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.supports_streaming = True
        self.logger = logging.getLogger(__name__)

    def create_chat_completion(
        self,
        system_message: Union[str, Dict[str, str]],
        user_prompt: str,
        message_history: Optional[List[Dict[str, str]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Create a chat completion using Ollama API.

        Args:
            system_message: System message or context as string or dict
            user_prompt: User prompt/query
            message_history: Optional list of previous messages
            model: Model to use (if None, uses default_model)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty parameter
            presence_penalty: Presence penalty parameter

        Returns:
            Response in standardized format compatible with OpenAI structure
        """
        # Extract system message content
        system_content = ""
        if isinstance(system_message, str):
            system_content = system_message
        elif system_message and "content" in system_message:
            system_content = system_message["content"]

        # Combine system message and history into a prompt
        combined_prompt = ""

        # Add system message if provided
        if system_content:
            combined_prompt += f"System: {system_content}\n\n"

        # Add message history if provided
        if message_history:
            for msg in message_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                combined_prompt += f"{role.capitalize()}: {content}\n\n"

        # Add the current user prompt
        combined_prompt += f"User: {user_prompt}\n\nAssistant:"

        # Prepare request payload for Ollama using generate endpoint
        payload = {
            "model": model or self.default_model,
            "prompt": combined_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
            },
        }

        # Add max_tokens only if specified
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        # Log request for debugging
        self.logger.debug(f"Sending request to Ollama API: {payload}")

        try:
            # Send request to Ollama using generate endpoint
            url = f"{self.api_url}/generate"
            self.logger.debug(f"Sending request to: {url}")
            response = requests.post(url, json=payload, timeout=self.timeout)

            # Check for HTTP errors
            response.raise_for_status()

            # Get JSON response
            ollama_response = response.json()

            # Log response for debugging
            self.logger.debug(f"Received response from Ollama: {ollama_response}")

            # If we got a valid response with a response field
            if "response" in ollama_response:
                # Convert to OpenAI-compatible format
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": ollama_response["response"],
                            },
                            "index": 0,
                            "finish_reason": "stop",  # Assuming completion for now
                        }
                    ],
                    "model": ollama_response.get("model", model or self.default_model),
                    "object": "chat.completion",
                    # Adding the raw Ollama response for debugging
                    "ollama_raw": ollama_response,
                }
            else:
                # If we didn't get the expected format, return an error
                raise ValueError(f"Unexpected response format from Ollama: {ollama_response}")

        except requests.RequestException as e:
            self.logger.error(f"HTTP error with Ollama API: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Ollama response as JSON: {str(e)}")
            self.logger.error(f"Response content: {response.text}")
            raise ValueError(f"Invalid JSON response from Ollama: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error in Ollama request: {str(e)}")
            raise

    def extract_content(self, response: Dict[str, Any]) -> str:
        """
        Extract content from Ollama response.

        Args:
            response: Response from Ollama API

        Returns:
            Extracted content as string
        """
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"Could not extract content from Ollama response: {e}")

    @property
    def supports_threads(self) -> bool:
        """
        Check if this handler supports threaded conversations.

        Returns:
            False as Ollama does not support threaded conversations in the OpenAI sense
        """
        return False
