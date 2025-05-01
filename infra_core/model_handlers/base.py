"""
Base Model Handler Interface

Defines the abstract interface for model handlers that can interact with
different model backends (OpenAI, LM Studio, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Union, Any, List


class BaseModelHandler(ABC):
    """
    Abstract base class for model handlers that interact with different model backends.

    All model handlers must implement the create_chat_completion method to ensure
    consistent interface across different backends.
    """

    @abstractmethod
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
        Create a chat completion using the model backend.

        Args:
            system_message: System message or context as string or dict
            user_prompt: User prompt/query
            message_history: Optional list of previous messages
            model: Model to use (if None, uses handler default)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            frequency_penalty: Frequency penalty parameter
            presence_penalty: Presence penalty parameter

        Returns:
            Response in a standardized format matching OpenAI's structure
        """
        pass

    @abstractmethod
    def extract_content(self, response: Dict[str, Any]) -> str:
        """
        Extract content from model response.

        Args:
            response: Response from model backend

        Returns:
            Extracted content as string
        """
        pass

    @property
    @abstractmethod
    def supports_threads(self) -> bool:
        """
        Check if this handler supports threaded conversations.

        Returns:
            True if threading is supported, False otherwise
        """
        pass
