"""
Prompt Templates Module

Provides Jinja2 template loading and rendering for agent system messages.
Centralizes all prompt management for consistent and maintainable agent creation.
"""

from pathlib import Path
from typing import Any, List, Optional
from jinja2 import Environment, FileSystemLoader


class PromptTemplateManager:
    """Manages Jinja2 templates for agent system messages"""

    def __init__(self, templates_dir: Optional[str] = None):
        """Initialize template manager with templates directory"""
        if templates_dir is None:
            # Default to prompts directory relative to project root
            current_dir = Path(__file__).parent.parent
            templates_dir = current_dir / "prompts"
        else:
            templates_dir = Path(templates_dir)

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)), trim_blocks=True, lstrip_blocks=True
        )

    def render_agent_prompt(
        self, agent_name: str, tool_specs: str = "", work_items_summary: str = "", **kwargs
    ) -> str:
        """
        Render an agent prompt template with context variables

        Args:
            agent_name: Name of the agent template file (without .j2 extension)
            tool_specs: MCP tool specifications string
            work_items_summary: Current work items context
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
        context = {"tool_specs": tool_specs, "work_items_summary": work_items_summary, **kwargs}

        return template.render(**context)

    def render_education_agent_prompt(
        self,
        agent_name: str,
        tool_specs: str = "",
        work_items_summary: str = "",
        ai_education_root_guid: str = "44bff8a7-6518-4514-92f9-49622fc72484",
        beginner_guid: str = "96adf1d9-d6f7-43d3-9d33-2f4e16a5fa2d",
        intermediate_guid: str = "5ae04999-1931-4530-8fa8-eaf7929ed83c",
        advanced_guid: str = "3ea67d6d-0e57-47e3-92ad-5daa6b1b8e3d",
        **kwargs,
    ) -> str:
        """
        Render an education-focused agent prompt with standard education GUIDs

        Args:
            agent_name: Name of the agent template file (without .j2 extension)
            tool_specs: MCP tool specifications string
            work_items_summary: Current work items context
            ai_education_root_guid: Root education knowledge block GUID
            beginner_guid: Beginner level GUID
            intermediate_guid: Intermediate level GUID
            advanced_guid: Advanced level GUID
            **kwargs: Additional template variables

        Returns:
            Rendered prompt string
        """
        education_context = {
            "ai_education_root_guid": ai_education_root_guid,
            "beginner_guid": beginner_guid,
            "intermediate_guid": intermediate_guid,
            "advanced_guid": advanced_guid,
            **kwargs,
        }

        return self.render_agent_prompt(
            agent_name=agent_name,
            tool_specs=tool_specs,
            work_items_summary=work_items_summary,
            **education_context,
        )

    def generate_tool_specs_from_mcp_tools(self, cogni_tools: List[Any]) -> str:
        """
        Generate tool specifications string from MCP tools list

        Args:
            cogni_tools: List of MCP tool objects

        Returns:
            Formatted tool specifications string
        """
        tool_specs = []
        for tool in cogni_tools:
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
**CRITICAL: All tools expect a single 'input' parameter containing JSON string with the actual arguments**

Example usage pattern:
- GetActiveWorkItems: input='{"limit": 10}' 
- CreateWorkItem: input='{"type": "task", "title": "My Task", "description": "..."}'

Tools:
""" + "\n".join(f"• {spec}" for spec in tool_specs[:12])  # Limit to top 12 tools

        if len(tool_specs_text) > 1400:  # Trim if too long
            tool_specs_text = tool_specs_text[:1400] + "\n... (more tools available)"

        return tool_specs_text


# Convenience functions for easy import
def render_work_reader_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render work reader agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt("work_reader", tool_specs, work_items_summary)


def render_priority_analyzer_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render priority analyzer agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt("priority_analyzer", tool_specs, work_items_summary)


def render_summary_writer_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render summary writer agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt("summary_writer", tool_specs, work_items_summary)


def render_cogni_leader_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render omnipresent Cogni leader agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt("cogni_leader", tool_specs, work_items_summary)


def render_dolt_commit_agent_prompt(tool_specs: str) -> str:
    """Render Dolt commit agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt("dolt_commit_agent", tool_specs, "")


# Education-specific convenience functions
def render_education_researcher_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render education researcher agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_education_agent_prompt(
        "education_researcher", tool_specs, work_items_summary
    )


def render_curriculum_analyst_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render curriculum analyst agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_education_agent_prompt(
        "curriculum_analyst", tool_specs, work_items_summary
    )


def render_education_reporter_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render education reporter agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_education_agent_prompt(
        "education_reporter", tool_specs, work_items_summary
    )


def render_cogni_education_leader_prompt(tool_specs: str, work_items_summary: str) -> str:
    """Render education-focused Cogni leader agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_education_agent_prompt(
        "cogni_education_leader", tool_specs, work_items_summary
    )


# Cleanup-specific convenience functions
def render_test_artifact_detector_prompt(
    tool_specs: str, work_items_summary: str, memory_overview_summary: str = ""
) -> str:
    """Render test artifact detector agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "test_artifact_detector",
        tool_specs,
        work_items_summary,
        memory_overview_summary=memory_overview_summary,
    )


def render_namespace_migrator_prompt(
    tool_specs: str, work_items_summary: str, memory_overview_summary: str = ""
) -> str:
    """Render namespace migrator agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "namespace_migrator",
        tool_specs,
        work_items_summary,
        memory_overview_summary=memory_overview_summary,
    )


def render_conflict_detector_prompt(
    tool_specs_text: str, work_items_summary: str, branch_inventory_summary: str = ""
) -> str:
    """Render conflict detector agent prompt with tools, work items, and branch inventory context"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "conflict_detector",
        tool_specs_text,
        work_items_summary,
        branch_inventory_summary=branch_inventory_summary,
    )


def render_branch_merger_prompt(
    tool_specs_text: str, work_items_summary: str, branch_inventory_summary: str = ""
) -> str:
    """Render branch merger agent prompt with tools, work items, and branch inventory context"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "branch_merger",
        tool_specs_text,
        work_items_summary,
        branch_inventory_summary=branch_inventory_summary,
    )


def render_dolt_outro_commit_generator_prompt(
    branch_name: str, status_data: str, diff_data: str, flow_context: str
) -> str:
    """Render Dolt outro commit message generator prompt"""
    manager = PromptTemplateManager()

    # Use render_agent_prompt with the outro-specific variables
    return manager.render_agent_prompt(
        "dolt_outro_commit_generator",
        tool_specs="",  # No tools needed for commit generation
        work_items_summary="",  # Not needed for commit generation
        branch_name=branch_name,
        status_data=status_data,
        diff_data=diff_data,
        flow_context=flow_context,
    )


# Playwright-specific convenience functions
def render_playwright_navigator_prompt(tool_specs: str, task_context: str = "") -> str:
    """Render playwright navigator agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "playwright_navigator", tool_specs, "", task_context=task_context
    )


def render_playwright_observer_prompt(tool_specs: str, task_context: str = "") -> str:
    """Render playwright observer agent prompt"""
    manager = PromptTemplateManager()
    return manager.render_agent_prompt(
        "playwright_observer", tool_specs, "", task_context=task_context
    )
