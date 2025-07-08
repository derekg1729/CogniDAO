"""
Model Binding Management for LangGraph Projects.

Provides centralized model binding, caching, and configuration management.
Support for both OpenAI and local Ollama models via provider abstraction.
"""

import os
from functools import lru_cache
from typing import Any

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from .logging_utils import get_logger

logger = get_logger(__name__)

# OpenAI model configurations
OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

# Local Ollama model configurations
OLLAMA_MODELS = ["qwen3:8b", "qwen3:4b", "qwen3:14b", "deepseek-coder"]

# Combined allowed models
ALLOWED_MODELS = OPENAI_MODELS + OLLAMA_MODELS

# Model mapping to actual identifiers
OPENAI_MODEL_MAPPING = {
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-3.5-turbo": "gpt-3.5-turbo-0125",
}


def get_model_handler():
    """
    Get the appropriate model handler based on LLM_PROVIDER environment variable.

    Returns:
        Model handler instance (OpenAI or Ollama-compatible)
    """
    model_provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if model_provider == "ollama":
        return get_ollama_handler()
    elif model_provider == "openai":
        return get_openai_handler()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {model_provider}. Use 'openai' or 'ollama'")


def get_ollama_handler():
    """Create Ollama-compatible ChatOpenAI handler."""
    model_name = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    ollama_url = os.getenv("OLLAMA_URL", "http://qwen-ollama:11434")

    if model_name not in OLLAMA_MODELS:
        logger.warning(f"Model {model_name} not in known OLLAMA_MODELS, proceeding anyway")

    return ChatOpenAI(
        model=model_name,
        openai_api_key="sk-local",  # Dummy key for Ollama
        openai_api_base=f"{ollama_url}/v1",
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.0")),
        streaming=True,
    )


def get_openai_handler():
    """Create OpenAI ChatOpenAI handler."""
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if model_name not in OPENAI_MODELS:
        raise ValueError(f"Unsupported OpenAI model {model_name}; choose from {OPENAI_MODELS}")

    actual_model = OPENAI_MODEL_MAPPING.get(model_name, model_name)

    return ChatOpenAI(
        model=actual_model,
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.0")),
        streaming=True,
    )


class ModelBindingManager:
    """Manages model binding and caching for LangGraph projects."""

    def __init__(
        self, allowed_models: list[str] | None = None, model_mapping: dict[str, str] | None = None
    ):
        """
        Initialize model binding manager.

        Args:
            allowed_models: List of allowed model names (legacy, now uses provider-based approach)
            model_mapping: Mapping of model names to actual identifiers (legacy)
        """
        # Maintain backward compatibility while using new provider system
        self.allowed_models = allowed_models or ALLOWED_MODELS
        self.model_mapping = model_mapping or OPENAI_MODEL_MAPPING

    def create_tools_signature(self, tools: list[BaseTool]) -> str:
        """Create a deterministic signature for tools to use as cache key."""
        return ",".join(sorted(getattr(t, "name", t.__class__.__name__) for t in tools))

    @lru_cache(maxsize=32)
    def _get_bound_model(
        self,
        model_signature: str,
        tools_signature: str,
        temperature: float = 0.0,
        streaming: bool = True,
    ) -> ChatOpenAI:
        """
        Get cached model instance with tools already bound.

        Args:
            model_signature: Signature representing the model configuration
            tools_signature: Deterministic signature for cache key
            temperature: Model temperature
            streaming: Whether to enable streaming

        Returns:
            ChatOpenAI instance (from OpenAI or Ollama provider)
        """
        # Get model handler based on provider
        base_model = get_model_handler()

        # Override temperature and streaming if different from defaults
        if temperature != base_model.temperature:
            base_model.temperature = temperature
        if streaming != getattr(base_model, "streaming", True):
            base_model.streaming = streaming

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
            model_name: Name of the model (ignored, uses provider-based selection)
            tools: List of tools to bind
            temperature: Model temperature
            streaming: Whether to enable streaming

        Returns:
            ChatOpenAI instance bound with tools
        """
        # Create signatures for caching
        provider = os.getenv("LLM_PROVIDER", "openai")
        model = os.getenv("OLLAMA_MODEL" if provider == "ollama" else "OPENAI_MODEL", "default")
        model_signature = f"{provider}:{model}:{temperature}:{streaming}"
        tools_signature = self.create_tools_signature(tools)

        # Get cached base model
        model = self._get_bound_model(model_signature, tools_signature, temperature, streaming)

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
    Get a cached, bound model instance using provider-based selection.

    Args:
        model_name: Name of the model (legacy parameter, actual model chosen via env vars)
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
        model_name: Name of the model (legacy, now determined by provider)
        temperature: Model temperature
        streaming: Whether to enable streaming

    Returns:
        Configuration dictionary
    """
    provider = os.getenv("LLM_PROVIDER", "openai")
    effective_model = os.getenv(
        "OLLAMA_MODEL" if provider == "ollama" else "OPENAI_MODEL",
        "qwen3:8b" if provider == "ollama" else "gpt-4o-mini",
    )

    return {
        "model_name": effective_model,
        "provider": provider,
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
