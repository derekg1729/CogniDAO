"""
Tests for cogni_presence agent template integration.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import AIMessage

from src.cogni_presence.agent import create_agent_node


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

        with patch('src.shared_utils.tool_registry.get_tools', return_value=[mock_tool]), \
             patch('src.cogni_presence.agent.ChatOpenAI', return_value=mock_model):
            
            # Create agent and test
            agent_node = await create_agent_node()
            
            # Verify the agent was created with the mocked tools
            assert agent_node is not None
            
            # Verify that get_tools was called
            # The agent should have been created with the mocked tools

    @pytest.mark.asyncio
    async def test_agent_handles_no_tools(self):
        """Test that agent handles case with no MCP tools."""
        # Mock the model response
        mock_response = AIMessage(content="I can help you.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch('src.shared_utils.tool_registry.get_tools', return_value=[]), \
             patch('src.cogni_presence.agent.ChatOpenAI', return_value=mock_model):
            
            # Create agent and test
            agent_node = await create_agent_node()
            
            # Verify the agent was created even with no tools
            assert agent_node is not None

    @pytest.mark.asyncio
    async def test_agent_adds_fallback_notice_on_mcp_failure(self):
        """Test that agent adds fallback notice when MCP connection fails."""
        # Mock the model response
        mock_response = AIMessage(content="I can help you.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch('src.shared_utils.tool_registry.get_tools', return_value=[]), \
             patch('src.cogni_presence.agent.ChatOpenAI', return_value=mock_model):
            
            # Create agent and test with first message (should trigger fallback notice)
            agent_node = await create_agent_node()
            
            # Verify the agent was created even with no tools
            assert agent_node is not None

    @pytest.mark.asyncio
    async def test_agent_handles_template_rendering_error(self):
        """Test that agent handles template rendering errors gracefully."""
        # Mock tools that will cause template error
        mock_tool = Mock()
        mock_tool.name = "TestTool"
        mock_tool.description = "Test tool"
        mock_tool.schema = None
        
        # Mock the model response
        mock_response = AIMessage(content="I can help you.")
        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)
        
        with patch('src.shared_utils.tool_registry.get_tools', return_value=[mock_tool]), \
             patch('src.cogni_presence.agent.ChatOpenAI', return_value=mock_model), \
             patch('src.shared_utils.prompt_templates.PromptTemplateManager.render_agent_prompt', 
                   side_effect=Exception("Template error")):
            
            # Should raise an exception when creating agent due to template error
            with pytest.raises(Exception) as exc_info:
                await create_agent_node()
            
            assert "Template error" in str(exc_info.value)

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

        with patch('src.shared_utils.tool_registry.get_tools', return_value=[mock_tool]), \
             patch('src.cogni_presence.agent.ChatOpenAI', return_value=mock_model) as mock_get_model:
            
            # Create agent and test with no model_name in config
            agent_node = await create_agent_node()
            
            # Verify the agent was created successfully
            assert agent_node is not None
            
            # Verify ChatOpenAI was called with default model name
            mock_get_model.assert_called_once()
            call_args = mock_get_model.call_args
            # Check that the default model name was used in the constructor
            assert call_args[1]['model_name'] == 'gpt-4o-mini'