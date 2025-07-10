"""
Tests for tool specifications functionality.
"""

from unittest.mock import Mock

from src.shared_utils.tool_specs import generate_tool_specs_from_mcp_tools


class TestToolSpecs:
    """Test the tool specifications functionality."""

    def test_generate_tool_specs_empty_list(self):
        """Test tool specs generation with empty list."""
        specs = generate_tool_specs_from_mcp_tools([])
        
        assert "No tools currently available" in specs
        assert "Available MCP Tools" in specs

    def test_generate_tool_specs_with_mock_tools(self):
        """Test tool specs generation with mock tools."""
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
        specs = generate_tool_specs_from_mcp_tools(tools)
        
        # Check content
        assert "Available MCP Tools" in specs
        assert "GetActiveWorkItems: Show current tasks" in specs
        assert "GlobalSemanticSearch: Search for information" in specs
        assert "branch: string (required)" in specs
        assert "namespace: string (optional)" in specs

    def test_generate_tool_specs_with_problematic_tools(self):
        """Test tool specs generation with tools that cause errors."""
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
        specs = generate_tool_specs_from_mcp_tools(tools)
        
        # Should handle errors gracefully - the error handling doesn't change the output format
        assert "ProblematicTool: Test tool" in specs
        assert "NormalTool: Normal tool" in specs

    def test_generate_tool_specs_truncation(self):
        """Test that tool specs are truncated if too long."""
        # Create many tools to test truncation
        tools = []
        for i in range(20):
            tool = Mock()
            tool.name = f"Tool{i}"
            tool.description = f"Description for tool {i}" * 10  # Make it long
            tool.schema = None
            tools.append(tool)
        
        specs = generate_tool_specs_from_mcp_tools(tools)
        
        # Should be truncated
        assert len(specs) <= 1450  # Should be under the limit
        assert "Available MCP Tools" in specs

    def test_generate_tool_specs_limits_to_12_tools(self):
        """Test that tool specs are limited to 12 tools."""
        # Create 15 tools
        tools = []
        for i in range(15):
            tool = Mock()
            tool.name = f"Tool{i}"
            tool.description = f"Description {i}"
            tool.schema = None
            tools.append(tool)
        
        specs = generate_tool_specs_from_mcp_tools(tools)
        
        # Should only include first 12 tools
        assert "Tool0:" in specs
        assert "Tool11:" in specs
        assert "Tool12:" not in specs
        assert "Tool14:" not in specs

