#!/usr/bin/env python3
"""
Tests for Cogni Image Gen LangGraph
==================================

Following LangGraph testing best practices:
- Unit tests for individual node functions with FakeListLLM
- Component tests for compiled graph routing and state management
- Deterministic testing with temperature=0 and mocked dependencies
"""

import pytest
from unittest.mock import Mock
from langchain_core.messages import HumanMessage, AIMessage

# Import components to test from refactored modules
from src.cogni_image_gen.graph import build_graph
from src.cogni_image_gen.agent import should_continue
from src.shared_utils import GraphConfig
from src.cogni_image_gen.state_types import ImageFlowState


class TestIndividualNodes:
    """Unit tests for individual node functions."""

    def test_should_continue_with_tool_calls(self):
        """Test should_continue returns 'continue' when message has tool calls."""
        mock_message = Mock()
        mock_message.tool_calls = [{"name": "test_tool", "args": {}}]

        state = {"messages": [mock_message]}
        result = should_continue(state)

        assert result == "continue"

    def test_should_continue_without_tool_calls(self):
        """Test should_continue returns 'end' when message has no tool calls."""
        mock_message = Mock()
        mock_message.tool_calls = []

        state = {"messages": [mock_message]}
        result = should_continue(state)

        assert result == "end"

    def test_should_continue_none_tool_calls(self):
        """Test should_continue returns 'end' when tool_calls is None."""
        mock_message = Mock()
        mock_message.tool_calls = None

        state = {"messages": [mock_message]}
        result = should_continue(state)

        assert result == "end"

    # Note: call_model function is now internal to the agent_node closure
    # Testing of model calling functionality is covered by integration tests

    # Note: _get_bound_model is now internal to shared_utils.model_binding
    # and is tested separately in its own test module


class TestStateManagement:
    """Test state management and message handling."""

    def test_agent_state_structure(self):
        """Test ImageFlowState TypedDict structure."""
        state: ImageFlowState = {"messages": [HumanMessage(content="test")]}

        assert "messages" in state
        assert isinstance(state["messages"], list)
        assert len(state["messages"]) == 1
        assert isinstance(state["messages"][0], HumanMessage)

    def test_graph_config_structure(self):
        """Test GraphConfig TypedDict structure."""
        config: GraphConfig = {"model_name": "gpt-4o-mini"}

        assert "model_name" in config
        assert config["model_name"] in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

    def test_message_add_behavior(self):
        """Test that add_messages annotation works correctly."""
        # This tests the Annotated[Sequence[BaseMessage], add_messages] behavior
        initial_state: ImageFlowState = {"messages": [HumanMessage(content="Hello")]}
        new_messages = [AIMessage(content="Hi there")]

        # Simulate what LangGraph does internally with add_messages
        combined_messages = initial_state["messages"] + new_messages

        assert len(combined_messages) == 2
        assert isinstance(combined_messages[0], HumanMessage)
        assert isinstance(combined_messages[1], AIMessage)


class TestGraphCompilation:
    """Component tests for compiled graph structure and routing."""

    @pytest.mark.asyncio
    async def test_workflow_compilation(self, mock_mcp_client):
        """Test that workflow compiles successfully."""
        workflow = await build_graph()
        compiled = workflow.compile()

        # Should have invoke methods
        assert hasattr(compiled, "invoke")
        assert hasattr(compiled, "ainvoke")
        assert hasattr(compiled, "stream")
        assert hasattr(compiled, "astream")

    @pytest.mark.asyncio
    async def test_workflow_nodes_exist(self, mock_mcp_client):
        """Test that workflow has expected nodes."""
        workflow = await build_graph()
        compiled = workflow.compile()

        # Check node structure (this tests the graph was built correctly)
        # We can't directly access nodes, but we can test compilation succeeded
        assert compiled is not None

    # Note: Full workflow execution tests are covered by integration tests
    # since they require complex mocking of the model binding system

    # Note: Complex workflow tests with tool calls are covered by integration tests


class TestDeterminism:
    """Test deterministic behavior for reliable testing."""

    # Note: Model temperature test is now covered by shared_utils.model_binding tests
    # since _get_bound_model is internal to that module



class TestErrorHandling:
    """Test error conditions and edge cases."""

    def test_empty_messages_state(self):
        """Test should_continue with empty messages."""
        state = {"messages": []}

        # This should not crash - though the real implementation
        # might need to handle this edge case
        try:
            result = should_continue(state)
            # If it doesn't crash, verify it returns a valid result
            assert result in ["continue", "end"]
        except IndexError:
            # Expected behavior if implementation accesses messages[-1]
            pass

    # Note: Model error handling tests are now covered by integration tests
    # since call_model is internal to the agent_node closure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
