"""
Shared pytest fixtures for flow-related tests.

Provides fixtures for testing prompt templates, Jinja2 rendering,
and agent configuration testing.
"""

import pytest
import tempfile
from pathlib import Path
from typing import Generator, List, Dict, Any
from unittest.mock import MagicMock

from infra_core.prompt_templates import PromptTemplateManager


@pytest.fixture(scope="session")
def temp_templates_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with test prompt templates."""
    with tempfile.TemporaryDirectory(prefix="test_prompts_") as temp_dir:
        templates_dir = Path(temp_dir)
        agent_dir = templates_dir / "agent"
        agent_dir.mkdir(parents=True)

        # Create test template files
        test_templates = {
            "_macros.j2": """
{# Test macro for tools #}
{% macro tool_specs(tools) -%}
## Test Tool Specs:
{%- for tool in tools[:3] %}
• {{ tool.name }}: {{ tool.description|default('No description') }}
{%- endfor %}
{%- endmacro %}

{# Test macro for work items #}
{% macro work_items_context(work_items_summary) -%}
{{ work_items_summary|default("## Test Context: No items") }}
{%- endmacro %}
""",
            "test_agent.j2": """
You are a test agent.

{{ tool_specs }}

{{ work_items_summary }}

Test variable: {{ test_var|default("default_value") }}
""",
            "education_agent.j2": """
You are an education agent.

Root GUID: {{ ai_education_root_guid }}
Beginner: {{ beginner_guid }}
Intermediate: {{ intermediate_guid }}

{{ tool_specs }}
""",
            "work_reader.j2": """
You read active work items from Cogni memory.

{{ tool_specs }}

{{ work_items_summary }}
""",
            "priority_analyzer.j2": """
You analyze work priorities.

{{ tool_specs }}

{{ work_items_summary }}
""",
            "summary_writer.j2": """
You write summaries.

{{ tool_specs }}

{{ work_items_summary }}
""",
            "cogni_leader.j2": """
You are the omnipresent Cogni leader.

{{ tool_specs }}

{{ work_items_summary }}
""",
            "dolt_commit_agent.j2": """
You handle Dolt commits.

{{ tool_specs }}
""",
        }

        # Write template files
        for filename, content in test_templates.items():
            template_path = agent_dir / filename
            template_path.write_text(content.strip())

        yield templates_dir


@pytest.fixture
def prompt_template_manager(temp_templates_dir: Path) -> PromptTemplateManager:
    """Create a PromptTemplateManager using the test templates directory."""
    return PromptTemplateManager(templates_dir=str(temp_templates_dir))


@pytest.fixture
def mock_tool() -> MagicMock:
    """Create a mock MCP tool for testing."""
    tool = MagicMock()
    tool.name = "TestTool"
    tool.description = "A test tool for testing"
    tool.schema = {
        "input_schema": {
            "properties": {"param1": {"type": "string"}, "param2": {"type": "integer"}},
            "required": ["param1"],
        }
    }
    return tool


@pytest.fixture
def mock_tools_list(mock_tool: MagicMock) -> List[MagicMock]:
    """Create a list of mock tools for testing."""
    tools = []

    # Create several mock tools
    for i in range(5):
        tool = MagicMock()
        tool.name = f"Tool{i}"
        tool.description = f"Description for tool {i}"
        tool.schema = {
            "input_schema": {
                "properties": {f"param{i}": {"type": "string"}},
                "required": [f"param{i}"] if i % 2 == 0 else [],
            }
        }
        tools.append(tool)

    return tools


@pytest.fixture
def sample_tool_specs() -> str:
    """Sample tool specifications string for testing."""
    return """## Available MCP Tools:
**CRITICAL: All tools expect a single 'input' parameter containing JSON string with the actual arguments**

Tools:
• TestTool: A test tool for testing | Args: param1: string (required), param2: integer (optional)
• Tool2: Another test tool
"""


@pytest.fixture
def sample_work_items_summary() -> str:
    """Sample work items summary for testing."""
    return """## Current Work Items Context:
- Task 1: Complete feature implementation (P1, in_progress)
- Task 2: Review code changes (P2, pending)
- Task 3: Update documentation (P3, blocked)
"""


@pytest.fixture
def education_guids() -> Dict[str, str]:
    """Standard education GUIDs used in templates."""
    return {
        "ai_education_root_guid": "44bff8a7-6518-4514-92f9-49622fc72484",
        "beginner_guid": "96adf1d9-d6f7-43d3-9d33-2f4e16a5fa2d",
        "intermediate_guid": "5ae04999-1931-4530-8fa8-eaf7929ed83c",
        "advanced_guid": "3ea67d6d-0e57-47e3-92ad-5daa6b1b8e3d",
    }


@pytest.fixture
def template_context() -> Dict[str, Any]:
    """Standard template context variables for testing."""
    return {
        "tool_specs": "## Test Tool Specs:\n• TestTool: Test description",
        "work_items_summary": "## Test Work Items:\n- Item 1\n- Item 2",
        "test_var": "test_value",
    }
