"""
Prompt Templates Module for LangGraph Projects

Provides Jinja2 template loading and rendering for LangGraph agent system messages.
Centralizes all prompt management for consistent and maintainable agent creation.
"""

from pathlib import Path
from typing import Any, List, Optional
from jinja2 import Environment, FileSystemLoader


class PromptTemplateManager:
    """Manages Jinja2 templates for LangGraph agent system messages"""

    def __init__(self, templates_dir: Optional[str] = None):
        """Initialize template manager with templates directory"""
        if templates_dir is None:
            # Default to templates directory in langgraph_projects
            current_dir = Path(__file__).parent.parent.parent
            templates_dir = current_dir / "templates"
        else:
            templates_dir = Path(templates_dir)

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)), trim_blocks=True, lstrip_blocks=True
        )

    def render_agent_prompt(
        self, agent_name: str, tool_specs: str = "", task_context: str = "", **kwargs
    ) -> str:
        """
        Render an agent prompt template with context variables

        Args:
            agent_name: Name of the agent template file (without .j2 extension)
            tool_specs: MCP tool specifications string
            task_context: Current task context
            **kwargs: Additional template variables

        Returns:
            Rendered prompt string
        """
        template_name = f"agent/{agent_name}.j2"

        try:
            template = self.env.get_template(template_name)
        except Exception as e:
            raise ValueError(f"Template {template_name} not found: {e}")

        # Standard context variables
        context = {"tool_specs": tool_specs, "task_context": task_context, **kwargs}

        return template.render(**context)

    def generate_tool_specs_from_mcp_tools(self, mcp_tools: List[Any]) -> str:
        """
        Generate tool specifications string from MCP tools list

        Args:
            mcp_tools: List of MCP tool objects

        Returns:
            Formatted tool specifications string
        """
        tool_specs = []
        for tool in mcp_tools:
            # Extract schema information safely
            schema_info = ""
            if hasattr(tool, "schema") and tool.schema:
                # Get input schema if available
                input_schema = tool.schema.get("input_schema", {})
                properties = input_schema.get("properties", {})
                required = input_schema.get("required", [])

                if properties:
                    args_info = []
                    for prop_name, prop_details in properties.items():
                        prop_type = prop_details.get("type", "unknown")
                        is_required = "(required)" if prop_name in required else "(optional)"
                        args_info.append(f"{prop_name}: {prop_type} {is_required}")
                    schema_info = f" | Args: {', '.join(args_info)}"

            # Build concise tool specification
            tool_spec = (
                f"{tool.name}: {getattr(tool, 'description', 'No description')}{schema_info}"
            )
            tool_specs.append(tool_spec)

        # Create formatted tool specs string (keep under 1.5k tokens)
        tool_specs_text = """## Available MCP Tools:

Example usage:
- navigate: {"url": "https://example.com"}
- screenshot: {"name": "page_capture.png"}

Tools:
""" + "\n".join(f"• {spec}" for spec in tool_specs[:12])  # Limit to top 12 tools

        if len(tool_specs_text) > 1400:  # Trim if too long
            tool_specs_text = tool_specs_text[:1400] + "\n... (more tools available)"

        return tool_specs_text


# Playwright-specific convenience functions
def render_playwright_navigator_prompt(
    tool_specs: str, 
    task_context: str = "", 
    target_url: str = "http://host.docker.internal:3000"
) -> str:
    """Render playwright navigator agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "playwright_navigator", 
        tool_specs, 
        task_context, 
        target_url=target_url
    )


def render_playwright_observer_prompt(
    tool_specs: str, 
    task_context: str = "", 
    target_url: str = "http://host.docker.internal:3000"
) -> str:
    """Render playwright observer agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "playwright_observer", 
        tool_specs, 
        task_context, 
        target_url=target_url
    )