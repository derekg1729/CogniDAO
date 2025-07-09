"""
Tests for cogni_presence agent template integration.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from src.cogni_presence.agent import create_agent_node
from src.shared_utils import CogniAgentState


class TestCogniPresenceAgentTemplates:
    """Test the cogni_presence agent template integration."""

    @pytest.mark.asyncio
    async def test_agent_uses_template_with_tools(self):
        """Test that agent uses template with dynamic tool specifications."""
        # Mock MCP tools
        mock_tool = Mock()
        mock_tool.name = "GetActiveWorkItems"
        mock_tool.description = "Show current tasks"
        mock_tool.schema = {
            "input_schema": {
                "properties": {
                    "branch": {"type": "string"},
                    "namespace": {"type": "string"}
                },
                "required": ["branch"]
            }
        }
        
        # Mock the model response
        mock_response = AIMessage(content="I can help you with your tasks.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch('src.cogni_presence.agent.get_mcp_tools_with_refresh', return_value=[mock_tool]), \
             patch('src.cogni_presence.agent.get_mcp_connection_info', return_value={
                 "state": "connected", 
                 "tools_count": 1,
                 "retry_count": 0,
                 "max_retries": 5
             }), \
             patch('src.cogni_presence.agent.get_cached_bound_model', return_value=mock_model):
            
            # Create agent and test
            agent_node = create_agent_node()
            
            state = CogniAgentState(messages=[HumanMessage(content="Hello")])
            config = {"configurable": {"model_name": "gpt-4o-mini"}}
            
            result = await agent_node(state, config)
            
            # Verify the model was called with templated system message
            mock_model.ainvoke.assert_called_once()
            call_args = mock_model.ainvoke.call_args[0][0]
            
            # Check that first message is SystemMessage with template content
            assert isinstance(call_args[0], SystemMessage)
            system_content = call_args[0].content
            
            # Verify template content is present
            assert "CogniDAO assistant" in system_content
            assert "GetActiveWorkItems" in system_content
            assert "Leave branch/namespace parameters empty" in system_content
            
            # Verify tool specs are included
            assert "GetActiveWorkItems: Show current tasks" in system_content
            assert "branch: string (required)" in system_content
            assert "namespace: string (optional)" in system_content
            
            # Verify user message is included
            assert isinstance(call_args[1], HumanMessage)
            assert call_args[1].content == "Hello"

    @pytest.mark.asyncio
    async def test_agent_handles_no_tools(self):
        """Test that agent handles case with no MCP tools."""
        # Mock the model response
        mock_response = AIMessage(content="I can help you.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch('src.cogni_presence.agent.get_mcp_tools_with_refresh', return_value=[]), \
             patch('src.cogni_presence.agent.get_mcp_connection_info', return_value={
                 "state": "failed", 
                 "tools_count": 0,
                 "retry_count": 5,
                 "max_retries": 5
             }), \
             patch('src.cogni_presence.agent.get_cached_bound_model', return_value=mock_model):
            
            # Create agent and test
            agent_node = create_agent_node()
            
            state = CogniAgentState(messages=[HumanMessage(content="Hello")])
            config = {"configurable": {"model_name": "gpt-4o-mini"}}
            
            result = await agent_node(state, config)
            
            # Verify the model was called
            mock_model.ainvoke.assert_called_once()
            call_args = mock_model.ainvoke.call_args[0][0]
            
            # Check system message content
            system_content = call_args[0].content
            
            # Should still have base template content
            assert "CogniDAO assistant" in system_content
            assert "No tools currently available" in system_content

    @pytest.mark.asyncio
    async def test_agent_adds_fallback_notice_on_mcp_failure(self):
        """Test that agent adds fallback notice when MCP connection fails."""
        # Mock the model response
        mock_response = AIMessage(content="I can help you.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch('src.cogni_presence.agent.get_mcp_tools_with_refresh', return_value=[]), \
             patch('src.cogni_presence.agent.get_mcp_connection_info', return_value={
                 "state": "failed", 
                 "tools_count": 0,
                 "retry_count": 5,
                 "max_retries": 5
             }), \
             patch('src.cogni_presence.agent.get_cached_bound_model', return_value=mock_model):
            
            # Create agent and test with first message (should trigger fallback notice)
            agent_node = create_agent_node()
            
            state = CogniAgentState(messages=[HumanMessage(content="Hello")])
            config = {"configurable": {"model_name": "gpt-4o-mini"}}
            
            result = await agent_node(state, config)
            
            # Check that fallback notice was added
            response_message = result["messages"][0]
            assert "limited tools due to MCP server connectivity" in response_message.content

    @pytest.mark.asyncio
    async def test_agent_handles_template_rendering_error(self):
        """Test that agent handles template rendering errors gracefully."""
        # Mock tools that will cause template error
        mock_tool = Mock()
        mock_tool.name = "TestTool"
        mock_tool.description = "Test tool"
        mock_tool.schema = None
        
        with patch('src.cogni_presence.agent.get_mcp_tools_with_refresh', return_value=[mock_tool]), \
             patch('src.cogni_presence.agent.get_mcp_connection_info', return_value={
                 "state": "connected", 
                 "tools_count": 1,
                 "retry_count": 0,
                 "max_retries": 5
             }), \
             patch('src.shared_utils.prompt_templates.PromptTemplateManager.render_agent_prompt', 
                   side_effect=Exception("Template error")):
            
            # Create agent and test
            agent_node = create_agent_node()
            
            state = CogniAgentState(messages=[HumanMessage(content="Hello")])
            config = {"configurable": {"model_name": "gpt-4o-mini"}}
            
            result = await agent_node(state, config)
            
            # Should return error message
            response_message = result["messages"][0]
            assert isinstance(response_message, AIMessage)
            assert "encountered an error" in response_message.content
            assert "Template error" in response_message.content

    @pytest.mark.asyncio
    async def test_agent_uses_default_model_name(self):
        """Test that agent uses default model name when none provided."""
        # Mock MCP tools
        mock_tool = Mock()
        mock_tool.name = "TestTool"
        mock_tool.description = "Test tool"
        mock_tool.schema = None
        
        # Mock the model response
        mock_response = AIMessage(content="I can help you.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch('src.cogni_presence.agent.get_mcp_tools_with_refresh', return_value=[mock_tool]), \
             patch('src.cogni_presence.agent.get_mcp_connection_info', return_value={
                 "state": "connected", 
                 "tools_count": 1,
                 "retry_count": 0,
                 "max_retries": 5
             }), \
             patch('src.cogni_presence.agent.get_cached_bound_model', return_value=mock_model) as mock_get_model:
            
            # Create agent and test with no model_name in config
            agent_node = create_agent_node()
            
            state = CogniAgentState(messages=[HumanMessage(content="Hello")])
            config = {"configurable": {}}  # No model_name
            
            result = await agent_node(state, config)
            
            # Verify default model name was used
            mock_get_model.assert_called_once()
            call_args = mock_get_model.call_args[0]
            assert call_args[0] == "gpt-4o-mini"  # Default model name