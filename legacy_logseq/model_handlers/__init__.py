"""
Model Handlers Package

Provides interfaces and implementations for different model backends.
"""

from legacy_logseq.model_handlers.base import BaseModelHandler
from legacy_logseq.model_handlers.openai_handler import OpenAIModelHandler
from legacy_logseq.model_handlers.ollama_handler import OllamaModelHandler

__all__ = ["BaseModelHandler", "OpenAIModelHandler", "OllamaModelHandler"]
