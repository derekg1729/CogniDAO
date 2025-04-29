"""
Tests for the CogniTool base class.
"""

import pytest
from pydantic import BaseModel, Field
from typing import Optional
from langchain.tools import Tool as LangChainTool

from experiments.src.memory_system.tools.cogni_tool import CogniTool


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
def echo_function(input_data: TestInput) -> TestOutput:
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
    assert result["result"] == "Processed: Hello"
    assert result["success"] is True


def test_invalid_input(test_tool):
    """Test tool with invalid input."""
    result = test_tool(invalid_field="test")
    assert result["success"] is False
    assert "error" in result
    assert "Validation error" in result["error"]


def test_langchain_conversion(test_tool):
    """Test conversion to LangChain tool."""
    lc_tool = test_tool.as_langchain_tool()
    assert isinstance(lc_tool, LangChainTool)
    assert lc_tool.name == "TestTool"
    assert lc_tool.description == "A test tool"
    assert lc_tool.args_schema == TestInput


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
    """Test automatic conversion of Pydantic models to dicts."""
    result = test_tool(text="Hello")
    assert isinstance(result, dict)
    assert "result" in result
    assert "success" in result


def test_error_handling(test_tool):
    """Test error handling in the tool wrapper."""
    # Test with missing required field
    result = test_tool()
    assert result["success"] is False
    assert "error" in result

    # Test with wrong type
    result = test_tool(text=123)  # Should be string
    assert result["success"] is False
    assert "error" in result
