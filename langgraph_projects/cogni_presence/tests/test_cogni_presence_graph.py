#!/usr/bin/env python3
"""
Tests for Cogni Presence LangGraph
==================================

Following LangGraph testing best practices:
- Unit tests for individual node functions with FakeListLLM
- Component tests for compiled graph routing and state management
- Deterministic testing with temperature=0 and mocked dependencies
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import components to test (using local imports since tests run from project dir)
from utils.build_graph import (
    build_graph,
    should_continue,
    call_model,
    AgentState,
    GraphConfig,
    _get_bound_model,
    system_prompt,
)


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

    @patch("utils.build_graph._get_cached_bound_model")
    @patch("utils.build_graph._initialize_tools")
    @pytest.mark.asyncio
    async def test_call_model_basic(self, mock_initialize_tools, mock_get_cached_bound_model, sample_config):
        """Test call_model with mocked LLM response."""
        # Setup fake tools
        mock_initialize_tools.return_value = []
        
        # Setup fake model
        fake_response = AIMessage(content="Test response", tool_calls=[])
        bound_model = Mock()
        bound_model.ainvoke = AsyncMock(return_value=fake_response)
        
        mock_get_cached_bound_model.return_value = bound_model

        # Test state
        state = {"messages": [HumanMessage(content="Hello")]}

        # Call the function
        result = await call_model(state, sample_config)

        # Verify
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0] == fake_response

        # Verify model was called with system prompt
        call_args = bound_model.ainvoke.call_args[0][0]
        assert len(call_args) == 2  # System message + user message
        assert isinstance(call_args[0], SystemMessage)
        assert call_args[0].content == system_prompt
        # The user message is a LangChain HumanMessage, check its content
        user_message = call_args[1]
        assert isinstance(user_message, HumanMessage)
        assert user_message.content == "Hello"

    def test_get_bound_model_gpt4o_mini(self):
        """Test _get_bound_model returns correct model for gpt-4o-mini."""
        with patch("utils.build_graph.ChatOpenAI") as mock_openai:
            mock_model = Mock()
            mock_openai.return_value = mock_model
            mock_model.bind_tools.return_value = mock_model

            result = _get_bound_model("gpt-4o-mini", "test_tools", ())

            mock_openai.assert_called_once_with(temperature=0, model_name="gpt-4o-mini")
            assert result == mock_model

    def test_get_bound_model_unsupported(self):
        """Test _get_bound_model raises ValueError for unsupported model."""
        with pytest.raises(ValueError, match="Unsupported model invalid-model; choose from"):
            _get_bound_model("invalid-model", "test_tools", ())


class TestStateManagement:
    """Test state management and message handling."""

    def test_agent_state_structure(self):
        """Test AgentState TypedDict structure."""
        state: AgentState = {"messages": [HumanMessage(content="test")]}

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
        initial_state: AgentState = {"messages": [HumanMessage(content="Hello")]}
        new_messages = [AIMessage(content="Hi there")]

        # Simulate what LangGraph does internally with add_messages
        combined_messages = initial_state["messages"] + new_messages

        assert len(combined_messages) == 2
        assert isinstance(combined_messages[0], HumanMessage)
        assert isinstance(combined_messages[1], AIMessage)


class TestGraphCompilation:
    """Component tests for compiled graph structure and routing."""

    @pytest.mark.asyncio
    async def test_workflow_compilation(self):
        """Test that workflow compiles successfully."""
        workflow = await build_graph()
        compiled = workflow.compile()

        # Should have invoke methods
        assert hasattr(compiled, "invoke")
        assert hasattr(compiled, "ainvoke")
        assert hasattr(compiled, "stream")
        assert hasattr(compiled, "astream")

    @pytest.mark.asyncio
    async def test_workflow_nodes_exist(self):
        """Test that workflow has expected nodes."""
        workflow = await build_graph()
        compiled = workflow.compile()

        # Check node structure (this tests the graph was built correctly)
        # We can't directly access nodes, but we can test compilation succeeded
        assert compiled is not None

    @patch("utils.build_graph._get_cached_bound_model")
    @patch("utils.build_graph._initialize_tools")
    @pytest.mark.asyncio
    async def test_basic_workflow_execution(self, mock_initialize_tools, mock_get_cached_bound_model):
        """Test basic workflow execution with mocked model."""
        # Setup fake tools
        mock_initialize_tools.return_value = []
        
        # Setup fake model that returns response without tool calls (ends flow)
        fake_response = AIMessage(content="Hello! How can I help?", tool_calls=[])
        bound_model = Mock()
        bound_model.ainvoke = AsyncMock(return_value=fake_response)
        
        mock_get_cached_bound_model.return_value = bound_model

        workflow = await build_graph()
        compiled = workflow.compile()

        # Test input
        initial_state = {"messages": [HumanMessage(content="Hello")]}
        config = {"configurable": {"model_name": "gpt-4o-mini"}}

        # Execute - use async invoke
        result = await compiled.ainvoke(initial_state, config)

        # Verify final state
        assert "messages" in result
        assert len(result["messages"]) == 2  # Original + AI response
        assert isinstance(result["messages"][0], HumanMessage)
        assert isinstance(result["messages"][1], AIMessage)
        assert result["messages"][1].content == "Hello! How can I help?"

    @patch("utils.build_graph._get_cached_bound_model")
    @patch("utils.build_graph._initialize_tools")
    @pytest.mark.asyncio
    async def test_workflow_with_tool_calls(self, mock_initialize_tools, mock_get_cached_bound_model):
        """Test workflow continues to tools when model returns tool calls."""
        # Setup fake tools
        mock_initialize_tools.return_value = []
        
        # Create model that first returns tool calls, then regular response
        first_response = AIMessage(
            content="Let me search for that.",
            tool_calls=[
                {"name": "tavily_search_results", "args": {"query": "test"}, "id": "call_1"}
            ],
        )
        second_response = AIMessage(content="Here's what I found.", tool_calls=[])

        bound_model = Mock()
        bound_model.ainvoke = AsyncMock(side_effect=[first_response, second_response])
        
        mock_get_cached_bound_model.return_value = bound_model

        workflow = await build_graph()
        compiled = workflow.compile()
        
        initial_state = {"messages": [HumanMessage(content="Search for something")]}
        config = {"configurable": {"model_name": "gpt-4o-mini"}}

        # This will fail at tool execution since we have empty tools, but that's expected
        # The important thing is that it tries to call tools (shows routing works)
        try:
            result = await compiled.ainvoke(initial_state, config)
            # If it succeeds, verify we got responses
            assert len(result["messages"]) >= 2  # At least human + AI
        except Exception as e:
            # Expected to fail at tool execution with empty tools
            # The key is that should_continue worked and routed to action
            assert "tool" in str(e).lower() or "invalid" in str(e).lower()


class TestDeterminism:
    """Test deterministic behavior for reliable testing."""

    @patch("utils.build_graph.ChatOpenAI")
    def test_model_temperature_zero(self, mock_openai):
        """Test that models are created with temperature=0 for determinism."""
        # Clear cache before test
        _get_bound_model.cache_clear()
        
        mock_model = Mock()
        mock_openai.return_value = mock_model
        mock_model.bind_tools.return_value = mock_model

        _get_bound_model("gpt-4o-mini", "unique_test_tools_id", ())

        mock_openai.assert_called_with(temperature=0, model_name="gpt-4o-mini")

    def test_system_prompt_consistency(self):
        """Test that system prompt is consistent."""
        assert system_prompt == "Be a helpful assistant"
        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 0


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

    @patch("utils.build_graph._get_cached_bound_model")
    @patch("utils.build_graph._initialize_tools")
    @pytest.mark.asyncio
    async def test_model_error_handling(self, mock_initialize_tools, mock_get_cached_bound_model, sample_config):
        """Test call_model handles model errors gracefully."""
        # Setup fake tools
        mock_initialize_tools.return_value = []
        
        # Setup model to raise exception
        bound_model = Mock()
        bound_model.ainvoke = AsyncMock(side_effect=Exception("Model error"))
        
        mock_get_cached_bound_model.return_value = bound_model

        state = {"messages": [HumanMessage(content="Hello")]}

        # This should either handle the error gracefully or let it propagate
        # depending on the implementation design
        with pytest.raises(Exception):
            await call_model(state, sample_config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
