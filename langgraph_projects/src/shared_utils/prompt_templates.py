"""
Prompt Templates Module for LangGraph Projects

This module is deprecated. Prompts have been moved to their respective agent directories.
Use local prompts.py files instead:
- playwright_poc/prompts.py
- cogni_presence/prompts.py

Tool specification utilities have been moved to src/shared_utils/tool_specs.py
"""

import warnings


def __getattr__(name):
    """Provide deprecation warnings for legacy imports"""
    if name in ["PLAYWRIGHT_NAVIGATOR_PROMPT", "COGNI_PRESENCE_PROMPT"]:
        warnings.warn(
            f"{name} has been moved to agent-specific prompts.py files. "
            "Import from the agent directory instead.",
            DeprecationWarning,
            stacklevel=2
        )
    elif name == "generate_tool_specs_from_mcp_tools":
        warnings.warn(
            "generate_tool_specs_from_mcp_tools has been moved to "
            "src.shared_utils.tool_specs. Update your imports.",
            DeprecationWarning,
            stacklevel=2
        )
    elif name in ["render_playwright_navigator_prompt", "render_playwright_observer_prompt"]:
        warnings.warn(
            f"{name} is deprecated. Use ChatPromptTemplate.partial() and .format() directly.",
            DeprecationWarning,
            stacklevel=2
        )
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")