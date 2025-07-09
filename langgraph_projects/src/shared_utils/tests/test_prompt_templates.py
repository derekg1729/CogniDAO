"""
Tests for prompt template functionality.
"""

import pytest
from unittest.mock import Mock
from pathlib import Path

from src.shared_utils.prompt_templates import (
    PromptTemplateManager,
    render_playwright_navigator_prompt,
    render_playwright_observer_prompt,
)


class TestPromptTemplateManager:
    """Test the PromptTemplateManager class."""

    def test_init_with_default_template_dir(self):
        """Test initialization with default template directory."""
        manager = PromptTemplateManager()
        expected_path = Path(__file__).parent.parent.parent.parent / "templates"
        assert manager.templates_dir == expected_path

    def test_init_with_custom_template_dir(self):
        """Test initialization with custom template directory."""
        custom_dir = "/tmp/custom_templates"
        manager = PromptTemplateManager(custom_dir)
        assert manager.templates_dir == Path(custom_dir)

    def test_render_cogni_presence_template(self):
        """Test rendering cogni_presence template."""
        manager = PromptTemplateManager()
        
        tool_specs = "• GetActiveWorkItems: Show current tasks"
        task_context = "Help user with project status"
        
        prompt = manager.render_agent_prompt(
            "cogni_presence",
            tool_specs=tool_specs,
            task_context=task_context
        )
        
        # Check base template content
        assert "CogniDAO assistant" in prompt
        assert "GetActiveWorkItems" in prompt
        assert "GlobalSemanticSearch" in prompt
        assert "Leave branch/namespace parameters empty" in prompt
        
        # Check dynamic content
        assert tool_specs in prompt
        assert task_context in prompt

    def test_render_template_with_empty_specs(self):
        """Test rendering template with empty tool specs."""
        manager = PromptTemplateManager()
        
        prompt = manager.render_agent_prompt(
            "cogni_presence",
            tool_specs="",
            task_context=""
        )
        
        # Base content should still be present
        assert "CogniDAO assistant" in prompt
        assert "GetActiveWorkItems" in prompt

    def test_render_template_with_additional_kwargs(self):
        """Test rendering template with additional context variables."""
        manager = PromptTemplateManager()
        
        prompt = manager.render_agent_prompt(
            "cogni_presence",
            tool_specs="• TestTool: Test description",
            task_context="Test context",
            custom_var="Custom value"
        )
        
        # Should include base content and additional variables are available to template
        assert "CogniDAO assistant" in prompt
        assert "TestTool" in prompt

    def test_render_nonexistent_template(self):
        """Test rendering a template that doesn't exist."""
        manager = PromptTemplateManager()
        
        with pytest.raises(ValueError, match="Template .* not found"):
            manager.render_agent_prompt("nonexistent_template")

    def test_generate_tool_specs_empty_list(self):
        """Test tool specs generation with empty list."""
        manager = PromptTemplateManager()
        
        specs = manager.generate_tool_specs_from_mcp_tools([])
        
        assert "No tools currently available" in specs
        assert "Available MCP Tools" in specs

    def test_generate_tool_specs_with_mock_tools(self):
        """Test tool specs generation with mock tools."""
        manager = PromptTemplateManager()
        
        # Create mock tools
        mock_tool1 = Mock()
        mock_tool1.name = "GetActiveWorkItems"
        mock_tool1.description = "Show current tasks"
        mock_tool1.schema = {
            "input_schema": {
                "properties": {
                    "branch": {"type": "string"},
                    "namespace": {"type": "string"}
                },
                "required": ["branch"]
            }
        }
        
        mock_tool2 = Mock()
        mock_tool2.name = "GlobalSemanticSearch"
        mock_tool2.description = "Search for information"
        mock_tool2.schema = None
        
        tools = [mock_tool1, mock_tool2]
        specs = manager.generate_tool_specs_from_mcp_tools(tools)
        
        # Check content
        assert "Available MCP Tools" in specs
        assert "GetActiveWorkItems: Show current tasks" in specs
        assert "GlobalSemanticSearch: Search for information" in specs
        assert "branch: string (required)" in specs
        assert "namespace: string (optional)" in specs

    def test_generate_tool_specs_with_problematic_tools(self):
        """Test tool specs generation with tools that cause errors."""
        manager = PromptTemplateManager()
        
        # Create a tool that will cause an error
        problematic_tool = Mock()
        problematic_tool.name = "ProblematicTool"
        problematic_tool.description = "Test tool"
        problematic_tool.schema = "invalid_schema"  # This will cause an error
        
        normal_tool = Mock()
        normal_tool.name = "NormalTool"
        normal_tool.description = "Normal tool"
        normal_tool.schema = None
        
        tools = [problematic_tool, normal_tool]
        specs = manager.generate_tool_specs_from_mcp_tools(tools)
        
        # Should handle errors gracefully
        assert "ProblematicTool: Available tool" in specs
        assert "NormalTool: Normal tool" in specs

    def test_generate_tool_specs_truncation(self):
        """Test that tool specs are truncated if too long."""
        manager = PromptTemplateManager()
        
        # Create many tools to test truncation
        tools = []
        for i in range(20):
            tool = Mock()
            tool.name = f"Tool{i}"
            tool.description = f"Description for tool {i}" * 10  # Make it long
            tool.schema = None
            tools.append(tool)
        
        specs = manager.generate_tool_specs_from_mcp_tools(tools)
        
        # Should be truncated
        assert len(specs) <= 1450  # Should be under the limit
        assert "Available MCP Tools" in specs

    def test_generate_tool_specs_limits_to_12_tools(self):
        """Test that tool specs are limited to 12 tools."""
        manager = PromptTemplateManager()
        
        # Create 15 tools
        tools = []
        for i in range(15):
            tool = Mock()
            tool.name = f"Tool{i}"
            tool.description = f"Description {i}"
            tool.schema = None
            tools.append(tool)
        
        specs = manager.generate_tool_specs_from_mcp_tools(tools)
        
        # Should only include first 12 tools
        assert "Tool0:" in specs
        assert "Tool11:" in specs
        assert "Tool12:" not in specs
        assert "Tool14:" not in specs


class TestPlaywrightPromptFunctions:
    """Test the Playwright-specific prompt functions."""

    def test_render_playwright_navigator_prompt(self):
        """Test rendering playwright navigator prompt."""
        tool_specs = "• navigate: Navigate to URL"
        task_context = "Navigate to login page"
        
        prompt = render_playwright_navigator_prompt(
            tool_specs=tool_specs,
            task_context=task_context,
            target_url="https://example.com"
        )
        
        # Should contain the tool specs and task context
        assert tool_specs in prompt
        assert task_context in prompt

    def test_render_playwright_observer_prompt(self):
        """Test rendering playwright observer prompt."""
        tool_specs = "• screenshot: Take screenshot"
        task_context = "Observe page changes"
        
        prompt = render_playwright_observer_prompt(
            tool_specs=tool_specs,
            task_context=task_context,
            target_url="https://example.com"
        )
        
        # Should contain the tool specs and task context
        assert tool_specs in prompt
        assert task_context in prompt

    def test_playwright_prompt_default_url(self):
        """Test playwright prompts with default URL."""
        prompt = render_playwright_navigator_prompt("• test: Test tool")
        
        # Should use default URL
        assert "http://host.docker.internal:3000" in prompt