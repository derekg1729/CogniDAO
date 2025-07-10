"""
Model Binding Management for LangGraph Projects.

Provides centralized model binding, caching, and configuration management.

TODO: currently unused by example agents :( 
"""

from functools import lru_cache
from typing import Any

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from .logging_utils import get_logger

logger = get_logger(__name__)

# Allowed model configurations
ALLOWED_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

# Model mapping to actual OpenAI identifiers
MODEL_MAPPING = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
}


class ModelBindingManager:
    """Manages model binding and caching for LangGraph projects."""

    def __init__(
        self, allowed_models: list[str] | None = None, model_mapping: dict[str, str] | None = None
    ):
        """
        Initialize model binding manager.

        Args:
            allowed_models: List of allowed model names
            model_mapping: Mapping of model names to actual identifiers
        """
        self.allowed_models = allowed_models or ALLOWED_MODELS
        self.model_mapping = model_mapping or MODEL_MAPPING

    def create_tools_signature(self, tools: list[BaseTool]) -> str:
        """Create a deterministic signature for tools to use as cache key."""
        return ",".join(sorted(getattr(t, "name", t.__class__.__name__) for t in tools))

    @lru_cache(maxsize=32)
    def _get_bound_model(
        self,
        model_name: str,
        tools_signature: str,
        temperature: float = 0.0,
        streaming: bool = True,
    ) -> ChatOpenAI:
        """
        Get cached model instance with tools already bound.

        Args:
            model_name: Name of the model to create
            tools_signature: Deterministic signature for cache key
            temperature: Model temperature
            streaming: Whether to enable streaming

        Returns:
            ChatOpenAI instance bound with tools
        """
        if model_name not in self.model_mapping:
            raise ValueError(f"Unsupported model {model_name}; choose from {self.allowed_models}")

        # Enable token-level streaming so downstream SSE emits deltas
        base_model = ChatOpenAI(
            temperature=temperature, model_name=self.model_mapping[model_name], streaming=streaming
        )

        # Note: tools binding happens in get_cached_bound_model
        return base_model

    def get_cached_bound_model(
        self,
        model_name: str,
        tools: list[BaseTool],
        temperature: float = 0.0,
        streaming: bool = True,
    ) -> ChatOpenAI:
        """
        Get a fully-bound model with tools, using caching for performance.

        Args:
            model_name: Name of the model to create
            tools: List of tools to bind
            temperature: Model temperature
            streaming: Whether to enable streaming

        Returns:
            ChatOpenAI instance bound with tools
        """
        tools_signature = self.create_tools_signature(tools)

        # Get cached base model
        model = self._get_bound_model(model_name, tools_signature, temperature, streaming)

        # Bind tools to the model
        return model.bind_tools(tools)

    def clear_cache(self):
        """Clear the model cache."""
        self._get_bound_model.cache_clear()


# Global model binding manager
_model_binding_manager: ModelBindingManager | None = None


def get_model_binding_manager() -> ModelBindingManager:
    """Get the global model binding manager."""
    global _model_binding_manager
    if _model_binding_manager is None:
        _model_binding_manager = ModelBindingManager()
    return _model_binding_manager


def get_cached_bound_model(
    model_name: str, tools: list[BaseTool], temperature: float = 0.0, streaming: bool = True
) -> ChatOpenAI:
    """
    Get a cached, bound model instance.

    Args:
        model_name: Name of the model to create
        tools: List of tools to bind
        temperature: Model temperature
        streaming: Whether to enable streaming

    Returns:
        ChatOpenAI instance bound with tools
    """
    manager = get_model_binding_manager()
    return manager.get_cached_bound_model(model_name, tools, temperature, streaming)


def create_model_config(
    model_name: str | None = None, temperature: float = 0.0, streaming: bool = True
) -> dict[str, Any]:
    """
    Create a model configuration dictionary.

    Args:
        model_name: Name of the model (defaults to gpt-4o-mini)
        temperature: Model temperature
        streaming: Whether to enable streaming

    Returns:
        Configuration dictionary
    """
    return {
        "model_name": model_name or "gpt-4o-mini",
        "temperature": temperature,
        "streaming": streaming,
    }


def validate_model_name(model_name: str) -> str:
    """
    Validate and normalize model name.

    Args:
        model_name: Model name to validate

    Returns:
        Validated model name

    Raises:
        ValueError: If model name is not supported
    """
    if model_name not in ALLOWED_MODELS:
        raise ValueError(f"Unsupported model {model_name}; choose from {ALLOWED_MODELS}")
    return model_name
