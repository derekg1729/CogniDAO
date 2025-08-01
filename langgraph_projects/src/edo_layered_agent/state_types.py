"""
State Types for Simple Cogni Agent.

Project-specific state definitions for the simple cogni agent workflow.
"""

from typing import Dict, Any, List
from src.shared_utils import BaseAgentState


class CogniAgentState(BaseAgentState):
    """State for Cogni presence agents."""

    # Inherits messages from BaseAgentState
    edo_current_event: Dict[str, Any] = {}  # Current event block JSON from edo loader
    edo_reasoning_context: List[Dict[str, Any]] = []  # Related blocks from edo loader
