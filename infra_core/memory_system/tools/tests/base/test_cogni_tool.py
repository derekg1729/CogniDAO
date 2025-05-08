"""
Tests for the CogniTool base class.
"""

import pytest
from pydantic import BaseModel, Field
from typing import Optional, get_type_hints
from langchain.tools import Tool as LangChainTool
from unittest.mock import Mock

from infra_core.memory_system.tools.base.cogni_tool import CogniTool


# Test Models
class TestInput(BaseModel):
    """Test input model."""

    text: str = Field(..., description="Test input text")
    number: Optional[int] = Field(None, description="Optional test number")


class TestOutput(BaseModel):
    """Test output model."""

    result: str = Field(..., description="Test result")
    success: bool = Field(..., description="Operation success")


# Helper function for testing
def echo_function(input_data: TestInput, memory_bank=None) -> TestOutput:
    """Echo function that processes input."""
    return TestOutput(result=f"Processed: {input_data.text}", success=True)


@pytest.fixture
def test_tool():
    """Create a test CogniTool instance."""
    return CogniTool(
        name="TestTool",
        description="A test tool",
        input_model=TestInput,
        output_model=TestOutput,
        function=echo_function,
        memory_linked=True,
    )


def test_tool_initialization(test_tool):
    """Test basic tool initialization."""
    assert test_tool.name == "TestTool"
    assert test_tool.description == "A test tool"
    assert test_tool.memory_linked is True
    assert test_tool.input_model == TestInput
    assert test_tool.output_model == TestOutput


def test_tool_schema(test_tool):
    """Test tool schema generation."""
    schema = test_tool.schema
    assert schema["name"] == "TestTool"
    assert schema["type"] == "function"
    assert schema["memory_linked"] is True
    assert "parameters" in schema
    assert "returns" in schema


def test_direct_invocation(test_tool):
    """Test direct tool invocation with kwargs."""
    result = test_tool(text="Hello")
    assert isinstance(result, TestOutput)
    assert result.result == "Processed: Hello"
    assert result.success is True


def test_invalid_input(test_tool):
    """Test tool with invalid input."""
    # Test with an unexpected field
    result = test_tool(invalid_field="test")
    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error"] == "Validation error"
    assert "details" in result


def test_langchain_conversion(test_tool):
    """Test conversion to LangChain tool."""
    lc_tool = test_tool.as_langchain_tool()
    assert isinstance(lc_tool, LangChainTool)
    assert lc_tool.name == "TestTool"
    assert lc_tool.description == "A test tool"
    # Compare type hints without internal attributes
    v1_hints = get_type_hints(lc_tool.args_schema)
    v2_hints = get_type_hints(TestInput)
    v1_fields = {k: v for k, v in v1_hints.items() if not k.startswith("_")}
    v2_fields = {k: v for k, v in v2_hints.items() if not k.startswith("_")}
    assert set(v1_fields.keys()) == set(v2_fields.keys())
    for field_name in v2_fields:
        assert v1_fields[field_name] == v2_fields[field_name]


def test_langchain_tool_memory_injection(test_tool):
    """Test that memory_bank is properly injected when using LangChain tool."""
    # Create mock memory bank
    mock_memory_bank = Mock()

    # Create LangChain tool with memory bank
    lc_tool = test_tool.as_langchain_tool(memory_bank=mock_memory_bank)

    # Call tool with text input
    result = lc_tool.run({"text": "test"})

    # Verify result
    assert isinstance(result, TestOutput)
    assert result.result == "Processed: test"
    assert result.success is True


def test_langchain_tool_memory_required(test_tool):
    """Test that memory-linked tools require memory_bank."""
    # Create LangChain tool
    lc_tool = test_tool.as_langchain_tool()

    # Call tool without memory_bank
    result = lc_tool.run({"text": "test"})

    # Verify error response
    assert isinstance(result, dict)
    assert result["success"] is False
    assert "memory_bank must be supplied" in result["error"]


def test_openai_schema(test_tool):
    """Test OpenAI function schema generation."""
    schema = test_tool.openai_schema()
    assert schema["name"] == "TestTool"
    assert "parameters" in schema
    assert "returns" in schema
    assert schema["parameters"] == TestInput.model_json_schema()
    assert schema["returns"] == TestOutput.model_json_schema()


def test_mcp_route(test_tool):
    """Test MCP route generation."""
    route = test_tool.to_mcp_route()
    assert "schema" in route
    assert "handler" in route
    assert route["schema"]["name"] == "TestTool"
    assert route["schema"]["memory_linked"] is True
    assert route["schema"]["inputSchema"] == TestInput.model_json_schema()
    assert route["schema"]["outputSchema"] == TestOutput.model_json_schema()


def test_pydantic_model_conversion(test_tool):
    """Test that the tool returns the correct Pydantic model instance."""
    result = test_tool(text="Hello")
    assert isinstance(result, TestOutput)
    assert result.result == "Processed: Hello"
    assert result.success is True


def test_error_handling(test_tool):
    """Test error handling in the tool wrapper for validation errors."""
    # Test with missing required field ('text')
    result = test_tool()
    assert isinstance(result, dict)  # Expect dict for validation errors
    assert result["success"] is False
    assert result["error"] == "Validation error"
    assert "details" in result

    # Test with wrong type for 'text'
    result = test_tool(text=123)  # Should be string
    assert isinstance(result, dict)  # Expect dict for validation errors
    assert result["success"] is False
    assert result["error"] == "Validation error"
    assert "details" in result
