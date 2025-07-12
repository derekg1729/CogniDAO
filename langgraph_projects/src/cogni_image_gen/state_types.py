"""
State Types for Cogni Image Generation.

Domain-specific state definitions for the image generation workflow.
"""

from src.shared_utils import BaseAgentState


class ImageFlowState(BaseAgentState):
    """Simplified state for image generation workflow focused on template variables."""

    # Core workflow fields
    user_request: str | None = None
    
    # Template variables (planner defines these 2 variables)
    agents_with_roles: list[dict] | None = None  # Agent configurations for the prompt template
    scene_focus: str | None = None  # Team activity/background context
    
    # Final prompt sent to DALL-E (for debugging)
    final_prompt: str | None = None
    
    # Output fields
    image_url: str | None = None
    assistant_response: str | None = None
    
    # Flow control
    retry_count: int = 0
    max_retries: int = 2