"""
Models package for Cogni experiments.

Contains model handler implementations for different backends.
NOTE: OllamaModelHandler has been moved to infra_core/model_handlers.
This is a compatibility layer to avoid breaking existing imports.
"""

# Forward imports to maintain compatibility with old code
from infra_core.model_handlers.ollama_handler import OllamaModelHandler

__all__ = ["OllamaModelHandler"]
