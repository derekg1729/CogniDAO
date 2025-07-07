#!/usr/bin/env python3
"""
Basic Tests for Playwright LangGraph
====================================

Simple tests for the LangGraph StateGraph structure and basic functionality.
Tests focus on graph compilation and structure without external dependencies.
"""

import pytest
from unittest.mock import Mock

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, END

# Import the graph components (using relative import since tests run from project dir)
from graph import (
    PlaywrightState,
    create_stategraph,
    should_continue,
)


@pytest.fixture
def sample_state():
    """Create a sample PlaywrightState for testing."""
    return PlaywrightState(
        messages=[HumanMessage(content="Take a screenshot of the current page")],
        tools_available=False,
        current_task="",
    )


class TestPlaywrightStateGraph:
    """Test the StateGraph structure and basic functionality."""

    def test_create_stategraph_structure(self):
        """Test that the StateGraph is created with correct structure."""
        workflow = create_stategraph()

        assert isinstance(workflow, StateGraph)

        # Check that nodes are configured (using public API)
        # We can verify this by attempting to compile the graph
        try:
            compiled = workflow.compile()
            assert compiled is not None
        except Exception as e:
            pytest.fail(f"Graph compilation failed: {e}")

    def test_compile_graph_basic(self):
        """Test basic graph compilation."""
        # Just test that we can create and compile a basic graph
        workflow = create_stategraph()
        compiled = workflow.compile()

        # Should be a compiled graph object
        assert hasattr(compiled, "invoke")
        assert hasattr(compiled, "ainvoke")
        assert hasattr(compiled, "astream")

    def test_should_continue_logic(self):
        """Test the conditional logic for workflow continuation."""
        # Test with tool calls
        mock_message_with_tools = Mock()
        mock_message_with_tools.tool_calls = [{"name": "test_tool", "args": {}}]

        state_with_tools = {"messages": [mock_message_with_tools]}
        result = should_continue(state_with_tools)
        assert result == "tools"

        # Test without tool calls
        mock_message_no_tools = Mock()
        mock_message_no_tools.tool_calls = []

        state_no_tools = {"messages": [mock_message_no_tools]}
        result = should_continue(state_no_tools)
        # LangGraph END constant is "__end__"
        assert result == END

    def test_playwright_state_structure(self, sample_state):
        """Test that PlaywrightState has the correct structure."""
        # Check required fields exist
        assert "messages" in sample_state
        assert "tools_available" in sample_state
        assert "current_task" in sample_state

        # Check types
        assert isinstance(sample_state["messages"], list)
        assert isinstance(sample_state["tools_available"], bool)
        assert isinstance(sample_state["current_task"], str)

        # Check initial values
        assert len(sample_state["messages"]) == 1
        assert sample_state["tools_available"] is False
        assert sample_state["current_task"] == ""


class TestStateManagement:
    """Test state management and message handling."""

    def test_message_types(self, sample_state):
        """Test that messages are properly typed."""
        assert isinstance(sample_state["messages"][0], HumanMessage)
        assert sample_state["messages"][0].content == "Take a screenshot of the current page"

    def test_state_updates(self, sample_state):
        """Test that state can be updated properly."""
        # Test updating tools_available
        new_state = {**sample_state, "tools_available": True}
        assert new_state["tools_available"] is True
        assert new_state["messages"] == sample_state["messages"]

        # Test adding messages
        ai_message = AIMessage(content="I'll help you take a screenshot")
        new_state_with_message = {
            **sample_state,
            "messages": sample_state["messages"] + [ai_message],
        }
        assert len(new_state_with_message["messages"]) == 2
        assert isinstance(new_state_with_message["messages"][1], AIMessage)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
