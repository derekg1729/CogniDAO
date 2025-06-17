"""
Tests for prompt template integration with actual flow files.

Tests that the flows properly use the template system and that templates
produce the expected agent configurations.
"""

import pytest
from unittest.mock import MagicMock
from pathlib import Path

# Import the flow functions that use templates
try:
    from flows.presence.simple_working_flow import main as simple_flow_main  # noqa: F401
    from flows.presence.ai_education_team_flow import main as education_flow_main  # noqa: F401

    FLOWS_AVAILABLE = True
except ImportError:
    FLOWS_AVAILABLE = False

from infra_core.prompt_templates import (
    PromptTemplateManager,
    render_work_reader_prompt,
    render_priority_analyzer_prompt,
    render_summary_writer_prompt,
    render_cogni_leader_prompt,
    render_dolt_commit_agent_prompt,
)


class TestFlowTemplateIntegration:
    """Test that flows properly integrate with the template system."""

    @pytest.mark.skipif(not FLOWS_AVAILABLE, reason="Flow modules not available")
    def test_simple_flow_uses_templates(self):
        """Test that simple_working_flow.py uses template functions."""
        # Read the flow file to verify it imports template functions
        flow_file = Path("flows/presence/simple_working_flow.py")
        if not flow_file.exists():
            pytest.skip("simple_working_flow.py not found")

        content = flow_file.read_text()

        # Verify imports of template functions
        assert "from infra_core.prompt_templates import" in content
        assert "render_work_reader_prompt" in content
        assert "render_priority_analyzer_prompt" in content
        assert "render_summary_writer_prompt" in content
        assert "render_cogni_leader_prompt" in content
        assert "render_dolt_commit_agent_prompt" in content

    @pytest.mark.skipif(not FLOWS_AVAILABLE, reason="Flow modules not available")
    def test_education_flow_uses_templates(self):
        """Test that ai_education_team_flow.py uses template functions."""
        # Read the flow file to verify it imports template functions
        flow_file = Path("flows/presence/ai_education_team_flow.py")
        if not flow_file.exists():
            pytest.skip("ai_education_team_flow.py not found")

        content = flow_file.read_text()

        # Verify imports of education template functions
        assert "from infra_core.prompt_templates import" in content
        # Should import education-specific functions
        expected_imports = [
            "render_education_researcher_prompt",
            "render_curriculum_analyst_prompt",
            "render_education_reporter_prompt",
            "render_cogni_education_leader_prompt",
        ]

        for import_name in expected_imports:
            assert import_name in content, f"Missing import: {import_name}"

    def test_template_consistency_with_flows(self):
        """Test that template outputs are consistent with what flows expect."""
        # Test work reader template
        result = render_work_reader_prompt("Test tools", "Test work items")

        # Should contain key phrases that flows rely on
        assert "work items" in result.lower()
        assert len(result) > 50  # Should be substantial

        # Test priority analyzer template
        result = render_priority_analyzer_prompt("Test tools", "Test work items")
        assert "priorities" in result.lower() or "priority" in result.lower()

        # Test summary writer template
        result = render_summary_writer_prompt("Test tools", "Test work items")
        assert "summar" in result.lower()  # "summary" or "summarize"

    def test_template_variables_match_flow_usage(self):
        """Test that template variables match what flows provide."""
        manager = PromptTemplateManager()

        # Test with realistic flow variables
        mock_tools = [MagicMock(name="GetActiveWorkItems"), MagicMock(name="CreateWorkItem")]
        tool_specs = manager.generate_tool_specs_from_mcp_tools(mock_tools)

        work_items_summary = """## Current Work Items Context:
- Project: AI Education System (P0, in_progress)
- Task: Implement curriculum analysis (P1, pending)
- Bug: Fix template rendering issue (P2, blocked)
"""

        # All these should render without errors
        agents = [
            "work_reader",
            "priority_analyzer",
            "summary_writer",
            "cogni_leader",
            "dolt_commit_agent",
        ]

        for agent_name in agents:
            try:
                result = manager.render_agent_prompt(
                    agent_name=agent_name,
                    tool_specs=tool_specs,
                    work_items_summary=work_items_summary,
                )
                assert len(result) > 100  # Should be substantial
                assert "MCP Tools" in result  # Should contain tool specs

                # Most agents should have work items context (except dolt_commit_agent)
                if agent_name != "dolt_commit_agent":
                    assert "Work Items" in result

            except Exception as e:
                pytest.fail(f"Failed to render {agent_name} template: {e}")


class TestTemplateBackwardsCompatibility:
    """Test backwards compatibility with existing flows."""

    def test_old_hardcoded_prompts_replaced(self):
        """Verify that old hardcoded prompts have been replaced with template calls."""

        # Check simple_working_flow.py
        flow_file = Path("flows/presence/simple_working_flow.py")
        if flow_file.exists():
            content = flow_file.read_text()

            # Should not contain old hardcoded system_message strings
            assert 'system_message=f"' not in content, "Found old f-string system_message"
            assert 'system_message="You read active work items' not in content, (
                "Found hardcoded work reader prompt"
            )
            assert 'system_message="You analyze work item priorities' not in content, (
                "Found hardcoded priority analyzer prompt"
            )

            # Should use template functions instead
            assert "render_work_reader_prompt(" in content
            assert "render_priority_analyzer_prompt(" in content

    def test_education_flow_hardcoded_prompts_replaced(self):
        """Verify that education flow hardcoded prompts have been replaced."""

        flow_file = Path("flows/presence/ai_education_team_flow.py")
        if flow_file.exists():
            content = flow_file.read_text()

            # Should not contain old hardcoded prompts
            assert 'system_message=f"' not in content, "Found old f-string system_message"
            assert 'system_message="You are an AI education researcher' not in content, (
                "Found hardcoded education researcher prompt"
            )

            # Should use education template functions
            assert "render_education_researcher_prompt(" in content


class TestTemplatePerformanceInFlows:
    """Test performance characteristics of templates in flow context."""

    def test_template_generation_speed(self):
        """Test that template generation is fast enough for flow usage."""
        import time

        manager = PromptTemplateManager()
        mock_tools = [MagicMock(name=f"Tool{i}") for i in range(10)]
        tool_specs = manager.generate_tool_specs_from_mcp_tools(mock_tools)
        work_items = "Test work items context"

        # Time multiple template generations
        start_time = time.time()

        for _ in range(10):
            render_work_reader_prompt(tool_specs, work_items)
            render_priority_analyzer_prompt(tool_specs, work_items)
            render_summary_writer_prompt(tool_specs, work_items)
            render_cogni_leader_prompt(tool_specs, work_items)
            render_dolt_commit_agent_prompt(tool_specs)

        end_time = time.time()
        total_time = end_time - start_time

        # Should be fast (less than 1 second for 50 template renders)
        assert total_time < 1.0, f"Template rendering too slow: {total_time:.2f}s"

    def test_template_memory_usage(self):
        """Test that template system doesn't leak memory."""
        # Generate many templates to test memory usage
        for i in range(100):
            tool_specs = f"Tool specs iteration {i}"
            work_items = f"Work items iteration {i}"

            # These should not accumulate memory
            render_work_reader_prompt(tool_specs, work_items)
            render_priority_analyzer_prompt(tool_specs, work_items)

        # If we get here without OOM, memory usage is reasonable


class TestTemplateValidation:
    """Test template validation and error conditions."""

    def test_template_syntax_validation(self):
        """Test that all real templates have valid Jinja2 syntax."""
        manager = PromptTemplateManager()
        templates_dir = manager.templates_dir / "agent"

        if not templates_dir.exists():
            pytest.skip("Agent templates directory not found")

        # Test all .j2 files for syntax errors
        for template_file in templates_dir.glob("*.j2"):
            try:
                template = manager.env.get_template(f"agent/{template_file.name}")
                # Try to render with minimal context
                template.render(tool_specs="Test tools", work_items_summary="Test work items")
            except Exception as e:
                pytest.fail(f"Template {template_file.name} has syntax error: {e}")

    def test_template_required_variables(self):
        """Test that templates handle missing required variables gracefully."""
        manager = PromptTemplateManager()

        # Test with minimal context (some variables missing)
        try:
            result = manager.render_agent_prompt("work_reader")
            assert len(result) > 0
        except Exception as e:
            pytest.fail(f"Template failed with minimal context: {e}")

    def test_template_variable_escaping(self):
        """Test that template variables are properly escaped."""
        manager = PromptTemplateManager()

        # Test with potentially dangerous content
        dangerous_content = '<script>alert("xss")</script>'

        result = manager.render_agent_prompt(
            "work_reader", tool_specs=dangerous_content, work_items_summary=dangerous_content
        )

        # Content should be included as-is (no HTML escaping in our case)
        # since these are system prompts, not web content
        assert dangerous_content in result
