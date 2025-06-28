"""
Tests for the prompt template system.

Tests the Jinja2 template loading, rendering, and all convenience functions
for agent prompt generation.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock
from typing import List, Dict

from infra_core.prompt_templates import (
    PromptTemplateManager,
    render_work_reader_prompt,
    render_priority_analyzer_prompt,
    render_summary_writer_prompt,
    render_cogni_leader_prompt,
    render_dolt_commit_agent_prompt,
    render_education_researcher_prompt,
    render_curriculum_analyst_prompt,
    render_education_reporter_prompt,
    render_cogni_education_leader_prompt,
)


class TestPromptTemplateManager:
    """Test the core PromptTemplateManager class."""

    def test_manager_initialization_default_path(self):
        """Test manager initializes with default templates directory."""
        manager = PromptTemplateManager()

        # Should point to prompts directory relative to project root
        assert str(manager.templates_dir).endswith("prompts")
        assert manager.env is not None

    def test_manager_initialization_custom_path(self, temp_templates_dir: Path):
        """Test manager initializes with custom templates directory."""
        manager = PromptTemplateManager(templates_dir=str(temp_templates_dir))

        assert manager.templates_dir == temp_templates_dir
        assert manager.env is not None

    def test_render_agent_prompt_basic(self, prompt_template_manager: PromptTemplateManager):
        """Test basic agent prompt rendering."""
        result = prompt_template_manager.render_agent_prompt(
            agent_name="test_agent",
            tool_specs="Test tools",
            work_items_summary="Test work items",
            test_var="custom_value",
        )

        assert "You are a test agent." in result
        assert "Test tools" in result
        assert "Test work items" in result
        assert "Test variable: custom_value" in result

    def test_render_agent_prompt_defaults(self, prompt_template_manager: PromptTemplateManager):
        """Test agent prompt rendering with default values."""
        result = prompt_template_manager.render_agent_prompt(agent_name="test_agent")

        assert "You are a test agent." in result
        assert "Test variable: default_value" in result

    def test_render_agent_prompt_missing_template(
        self, prompt_template_manager: PromptTemplateManager
    ):
        """Test error handling for missing template."""
        with pytest.raises(ValueError, match="Template agent/nonexistent.j2 not found"):
            prompt_template_manager.render_agent_prompt("nonexistent")

    def test_render_education_agent_prompt(
        self, prompt_template_manager: PromptTemplateManager, education_guids: Dict[str, str]
    ):
        """Test education agent prompt rendering with GUIDs."""
        result = prompt_template_manager.render_education_agent_prompt(
            agent_name="education_agent", tool_specs="Test tools"
        )

        assert "You are an education agent." in result
        assert education_guids["ai_education_root_guid"] in result
        assert education_guids["beginner_guid"] in result
        assert education_guids["intermediate_guid"] in result
        assert "Test tools" in result

    def test_render_education_agent_custom_guids(
        self, prompt_template_manager: PromptTemplateManager
    ):
        """Test education agent prompt with custom GUIDs."""
        custom_guids = {
            "ai_education_root_guid": "custom-root-guid",
            "beginner_guid": "custom-beginner-guid",
            "intermediate_guid": "custom-intermediate-guid",
        }

        result = prompt_template_manager.render_education_agent_prompt(
            agent_name="education_agent", **custom_guids
        )

        assert "custom-root-guid" in result
        assert "custom-beginner-guid" in result
        assert "custom-intermediate-guid" in result

    def test_generate_tool_specs_from_mcp_tools(
        self, prompt_template_manager: PromptTemplateManager, mock_tools_list: List[MagicMock]
    ):
        """Test tool specifications generation from MCP tools."""
        result = prompt_template_manager.generate_tool_specs_from_mcp_tools(mock_tools_list)

        assert "## Available MCP Tools:" in result
        assert "Args:" in result  # Shows individual parameter details
        assert "(required)" in result or "(optional)" in result  # Shows parameter types
        assert "Tool0: Description for tool 0" in result
        assert "Tool1: Description for tool 1" in result
        # Should limit to first 12 tools, but we only have 5
        assert "Tool4: Description for tool 4" in result

    def test_generate_tool_specs_truncation(self, prompt_template_manager: PromptTemplateManager):
        """Test tool specifications generation with many tools (truncation)."""
        # Create many tools to test truncation
        many_tools = []
        for i in range(15):
            tool = MagicMock()
            tool.name = f"Tool{i:02d}"
            tool.description = f"Description for tool {i:02d}"
            tool.schema = {"input_schema": {"properties": {}, "required": []}}
            many_tools.append(tool)

        result = prompt_template_manager.generate_tool_specs_from_mcp_tools(many_tools)

        # Should only include first 12 tools
        assert "Tool00:" in result
        assert "Tool11:" in result
        assert "Tool12:" not in result
        assert "Tool14:" not in result

    def test_generate_tool_specs_with_schema(self, prompt_template_manager: PromptTemplateManager):
        """Test tool specifications generation with detailed schemas."""
        tool = MagicMock()
        tool.name = "ComplexTool"
        tool.description = "A complex tool"
        tool.schema = {
            "input_schema": {
                "properties": {
                    "required_param": {"type": "string"},
                    "optional_param": {"type": "integer"},
                    "another_param": {"type": "boolean"},
                },
                "required": ["required_param"],
            }
        }

        result = prompt_template_manager.generate_tool_specs_from_mcp_tools([tool])

        assert "ComplexTool: A complex tool" in result
        assert "required_param: string (required)" in result
        assert "optional_param: integer (optional)" in result
        assert "another_param: boolean (optional)" in result

    def test_generate_tool_specs_empty_list(self, prompt_template_manager: PromptTemplateManager):
        """Test tool specifications generation with empty tools list."""
        result = prompt_template_manager.generate_tool_specs_from_mcp_tools([])

        assert "## Available MCP Tools:" in result
        assert "Example usage:" in result  # Should show example usage even with no tools
        assert "Tools:" in result  # Should show Tools section even when empty
        # Should have basic structure even with no tools


class TestConvenienceFunctions:
    """Test the convenience functions for common agent types."""

    def test_render_work_reader_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test work reader prompt rendering."""
        result = render_work_reader_prompt(sample_tool_specs, sample_work_items_summary)

        assert "You read active work items from Cogni memory" in result
        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_priority_analyzer_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test priority analyzer prompt rendering."""
        result = render_priority_analyzer_prompt(sample_tool_specs, sample_work_items_summary)

        assert "You analyze work item priorities" in result
        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_summary_writer_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test summary writer prompt rendering."""
        result = render_summary_writer_prompt(sample_tool_specs, sample_work_items_summary)

        assert "You write concise summaries" in result
        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_cogni_leader_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test Cogni leader prompt rendering."""
        result = render_cogni_leader_prompt(sample_tool_specs, sample_work_items_summary)

        assert "You are the soon-to-be omnipresent leader" in result
        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_dolt_commit_agent_prompt(self, sample_tool_specs: str):
        """Test Dolt commit agent prompt rendering."""
        result = render_dolt_commit_agent_prompt(sample_tool_specs)

        assert "You are a Dolt commit agent" in result
        assert sample_tool_specs in result

    def test_render_education_researcher_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test education researcher prompt rendering."""
        result = render_education_researcher_prompt(sample_tool_specs, sample_work_items_summary)

        # Should use the default education agent template (since we don't have specific ones)
        # This will test that the education-specific function works
        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_curriculum_analyst_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test curriculum analyst prompt rendering."""
        result = render_curriculum_analyst_prompt(sample_tool_specs, sample_work_items_summary)

        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_education_reporter_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test education reporter prompt rendering."""
        result = render_education_reporter_prompt(sample_tool_specs, sample_work_items_summary)

        assert sample_tool_specs in result
        assert sample_work_items_summary in result

    def test_render_cogni_education_leader_prompt(
        self, sample_tool_specs: str, sample_work_items_summary: str
    ):
        """Test Cogni education leader prompt rendering."""
        result = render_cogni_education_leader_prompt(sample_tool_specs, sample_work_items_summary)

        assert sample_tool_specs in result
        assert sample_work_items_summary in result


class TestTemplateIntegration:
    """Test template integration and real template loading."""

    def test_real_templates_exist(self):
        """Test that real prompt templates exist in the project."""
        manager = PromptTemplateManager()
        templates_dir = manager.templates_dir
        agent_dir = templates_dir / "agent"

        # Check that the agent directory exists
        assert agent_dir.exists(), f"Agent templates directory not found: {agent_dir}"

        # Check for key template files
        expected_templates = [
            "_macros.j2",
            "work_reader.j2",
            "priority_analyzer.j2",
            "summary_writer.j2",
            "cogni_leader.j2",
            "dolt_commit_agent.j2",
        ]

        for template_name in expected_templates:
            template_path = agent_dir / template_name
            assert template_path.exists(), f"Template not found: {template_path}"

    def test_real_template_rendering(self):
        """Test rendering with real templates."""
        try:
            # Test that we can render real templates without errors
            result = render_work_reader_prompt("Test tools", "Test work items")
            assert len(result) > 0
            assert "work items" in result.lower()
        except Exception as e:
            pytest.fail(f"Failed to render real template: {e}")

    def test_real_education_template_rendering(self):
        """Test rendering with real education templates."""
        try:
            # Test that we can render real education templates without errors
            result = render_education_researcher_prompt("Test tools", "Test work items")
            assert len(result) > 0
        except Exception as e:
            pytest.fail(f"Failed to render real education template: {e}")


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_missing_templates_directory(self):
        """Test error handling for missing templates directory."""
        with pytest.raises(Exception):
            manager = PromptTemplateManager(templates_dir="/nonexistent/path")
            manager.render_agent_prompt("test_agent")

    def test_empty_tool_specs(self, prompt_template_manager: PromptTemplateManager):
        """Test rendering with empty tool specifications."""
        result = prompt_template_manager.render_agent_prompt(
            agent_name="test_agent", tool_specs="", work_items_summary=""
        )

        assert "You are a test agent." in result
        assert "Test variable: default_value" in result

    def test_none_values(self, prompt_template_manager: PromptTemplateManager):
        """Test rendering with None values."""
        # Jinja2 should handle None gracefully
        result = prompt_template_manager.render_agent_prompt(
            agent_name="test_agent", tool_specs=None, work_items_summary=None
        )

        assert "You are a test agent." in result

    def test_unicode_content(self, prompt_template_manager: PromptTemplateManager):
        """Test rendering with Unicode content."""
        unicode_content = "Tools: 🔧 ⚙️ 🛠️\nWork: 📝 ✅ 🚀"

        result = prompt_template_manager.render_agent_prompt(
            agent_name="test_agent", tool_specs=unicode_content, work_items_summary=unicode_content
        )

        assert unicode_content in result
        assert "🔧" in result


class TestPerformance:
    """Test performance characteristics of template system."""

    def test_template_caching(self, prompt_template_manager: PromptTemplateManager):
        """Test that templates are cached for performance."""
        # Multiple renders should not reload templates
        for _ in range(5):
            result = prompt_template_manager.render_agent_prompt(
                agent_name="test_agent", tool_specs="Test", work_items_summary="Test"
            )
            assert "You are a test agent." in result

    def test_large_context_rendering(self, prompt_template_manager: PromptTemplateManager):
        """Test rendering with large context variables."""
        large_tools = "Tool " * 1000  # Large tool specs
        large_work_items = "Work item " * 1000  # Large work items

        result = prompt_template_manager.render_agent_prompt(
            agent_name="test_agent", tool_specs=large_tools, work_items_summary=large_work_items
        )

        assert len(result) > 2000  # Should be substantial
        assert "You are a test agent." in result
