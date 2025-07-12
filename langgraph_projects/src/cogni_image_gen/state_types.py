"""
State Types for Cogni Image Generation.

Domain-specific state definitions for the image generation workflow.
"""

import operator
from typing import Annotated, Literal
from src.shared_utils import BaseAgentState


class ImageFlowState(BaseAgentState):
    """Simplified state for image generation workflow focused on template variables."""

    # Core workflow fields
    user_request: str | None = None
    
    # Template variables (planner defines these 2 variables)
    # Using default behavior (no annotation) for overwrite semantics
    agents_with_roles: list[dict] | None = None  # Agent configurations for the prompt template
    scene_focus: str | None = None  # Team activity/background context
    
    # Final prompt sent to DALL-E (for debugging)
    final_prompt: str | None = None
    
    # Output fields
    image_url: str | None = None
    assistant_response: str | None = None
    
    # Flow control for reviewer feedback loop
    attempt: Annotated[int, operator.add] = 0  # Auto-increments each time reviewer runs
    needs_retry: bool = False  # Flag set by reviewer to request another planner pass
    score: float | None = None  # Quality score from reviewer
    issues: list[str] = []  # Issues identified by reviewer (overwrites)
    suggestions: list[str] = []  # Improvement suggestions from reviewer (overwrites)
    
    # Human-in-the-loop control fields
    decision: Literal['approve', 'revise'] | None = None  # Human's approve/revise decision
    planner_feedback: str | None = None  # Human feedback for planner improvement
    last_interrupt_id: str | None = None  # Track interrupt ID for resume operations