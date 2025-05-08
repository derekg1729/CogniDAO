"""
CrewAI adapter for Cogni's memory system.

This module provides adapter classes that integrate Cogni's memory system with CrewAI:
- CogniMemoryStorage: Provides memory tools for CrewAI agents using Cogni's StructuredMemoryBank
"""

from __future__ import annotations

from .memory import CogniMemoryStorage

__all__ = [
    "CogniMemoryStorage",
]
