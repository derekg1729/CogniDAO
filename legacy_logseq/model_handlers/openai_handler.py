"""
OpenAI Model Handler

Implementation of BaseModelHandler that works with OpenAI API,
wrapping the existing functionality from openai_handler.py.
"""

from typing import Dict, Optional, Union, Any, List, Tuple

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI package not installed. Install with 'pip install openai'")

from legacy_logseq.model_handlers.base import BaseModelHandler
from legacy_logseq.openai_handler import (
    initialize_openai_client,
    create_completion,
    extract_content as openai_extract_content,
    create_thread,
    thread_completion,
)


class OpenAIModelHandler(BaseModelHandler):
    """
    OpenAI model handler implementation.

    Wraps existing OpenAI functionality to conform to the BaseModelHandler interface.
    """

    def __init__(
        self,
        default_model: str = "gpt-4",
        api_key: Optional[str] = None,
        client: Optional[OpenAI] = None,
    ):
        """
        Initialize OpenAI model handler.

        Args:
            default_model: Default model to use if not specified in method calls
            api_key: OpenAI API key (will use env var or Prefect Secret if None)
            client: Existing OpenAI client to use (will create new if None)
        """
        self.default_model = default_model
        self._api_key = api_key
        self._client = client

    @property
    def client(self) -> OpenAI:
        """
        Get or initialize OpenAI client.

        Returns:
            OpenAI client instance
        """
        if self._client is None:
            if self._api_key:
                self._client = OpenAI(api_key=self._api_key)
            else:
                self._client = initialize_openai_client()
        return self._client

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
        Create a chat completion using OpenAI API.

        Args:
            system_message: System message or context as string or dict
            user_prompt: User prompt/query
            message_history: Optional list of previous messages
            model: Model to use (defaults to self.default_model if None)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty parameter
            presence_penalty: Presence penalty parameter

        Returns:
            Response from OpenAI API
        """
        return create_completion(
            client=self.client,
            system_message=system_message,
            user_prompt=user_prompt,
            message_history=message_history,
            model=model or self.default_model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
        )

    def extract_content(self, response: Dict[str, Any]) -> str:
        """
        Extract content from OpenAI API response.

        Args:
            response: Response from OpenAI API

        Returns:
            Extracted content as string
        """
        return openai_extract_content(response)

    @property
    def supports_threads(self) -> bool:
        """
        Check if this handler supports threaded conversations.

        Returns:
            True as OpenAI supports threads
        """
        return True

    def create_thread(self, instructions: str, model: str = "gpt-4-turbo") -> Tuple[str, str]:
        """
        Create a thread and assistant for reuse across multiple completion calls.

        Args:
            instructions: System instructions for the assistant
            model: Model to use for the assistant

        Returns:
            Tuple of (thread_id, assistant_id)
        """
        return create_thread(self.client, instructions, model)

    def thread_completion(
        self,
        thread_id: str,
        assistant_id: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """
        Send a message to a thread and get the assistant's response.

        Args:
            thread_id: ID of the thread to use
            assistant_id: ID of the assistant to use
            user_prompt: User message to send

        Returns:
            Response in standardized format
        """
        return thread_completion(
            client=self.client,
            thread_id=thread_id,
            assistant_id=assistant_id,
            user_prompt=user_prompt,
        )
