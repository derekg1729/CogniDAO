"""
Test EDO agent metadata functionality.
Tests the new agent_id filtering and metadata features.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch
import pytest
from langgraph.types import RunnableConfig

from src.shared_utils.edo_hooks import edo_event_loader_node, next_edo_log_creator_node


@pytest.fixture
def mock_config():
    """Mock RunnableConfig with thread_id."""
    return RunnableConfig(configurable={"thread_id": "test_thread_123"})


@pytest.fixture
def mock_state():
    """Mock state with messages."""
    return {
        "messages": [type('Message', (), {'content': 'Test decision content'})()],
        "past_agent_edo_log": {
            "id": "event_123",
            "title": "Test Event",
            "content": "Test event content"
        }
    }


@pytest.mark.asyncio
async def test_edo_event_loader_filters_by_agent_id(mock_config):
    """Test that edo_event_loader_node filters by agent_id."""
    mock_get_memory_tool = AsyncMock()
    mock_get_memory_tool.name = "GetMemoryBlock"
    mock_get_memory_tool.ainvoke.return_value = json.dumps({
        "success": True,
        "blocks": [
            {
                "id": "block_1",
                "title": "Test Block",
                "metadata": {"x_agent_id": "test_agent"}
            }
        ]
    })
    
    with patch('src.shared_utils.edo_hooks.get_tools') as mock_get_tools:
        mock_get_tools.return_value = [mock_get_memory_tool]
        
        await edo_event_loader_node(
            state={},
            config=mock_config,
            agent_id="test_agent"
        )
        
        # Verify agent_id was used in metadata filter
        mock_get_memory_tool.ainvoke.assert_called_once()
        call_args = mock_get_memory_tool.ainvoke.call_args[0][0]
        
        assert "metadata_filters" in call_args
        assert "test_agent" in call_args["metadata_filters"]


@pytest.mark.asyncio
async def test_next_edo_log_creator_includes_metadata(mock_config, mock_state):
    """Test that next_edo_log_creator_node includes agent metadata."""
    mock_create_memory_tool = AsyncMock()
    mock_create_memory_tool.name = "CreateMemoryBlock"
    mock_create_memory_tool.ainvoke.return_value = json.dumps({
        "success": True,
        "id": "log_123"
    })
    
    mock_create_link_tool = AsyncMock()
    mock_create_link_tool.name = "CreateBlockLink"
    mock_create_link_tool.ainvoke.return_value = json.dumps({"success": True})
    
    # Add memory refs to state so next_edo_log_creator can find previous log
    test_state = {**mock_state, "relevant_memory_block_refs": {"previous_agent_edo_log": "prev_log_123"}}
    
    with patch('src.shared_utils.edo_hooks.get_tools') as mock_get_tools:
        mock_get_tools.return_value = [mock_create_memory_tool, mock_create_link_tool]
        
        await next_edo_log_creator_node(
            state=test_state,
            config=mock_config,
            agent_id="test_agent"
        )
        
        # Verify log creation with agent metadata
        mock_create_memory_tool.ainvoke.assert_called_once()
        
        # Check log creation call
        log_call = mock_create_memory_tool.ainvoke.call_args[0][0]
        
        assert log_call["x_agent_id"] == "test_agent"
        assert "test_thread_123" in log_call["title"]
        assert "x_timestamp" in log_call
        assert log_call["type"] == "log"


@pytest.mark.asyncio
async def test_partial_binding_integration():
    """Test that functools.partial binding works correctly."""
    from functools import partial
    
    # Create partial function as done in nodes.py
    bound_loader = partial(edo_event_loader_node, agent_id="edo_layered_agent")
    
    mock_get_memory_tool = AsyncMock()
    mock_get_memory_tool.name = "GetMemoryBlock"
    mock_get_memory_tool.ainvoke.return_value = json.dumps({
        "success": True,
        "blocks": []
    })
    
    with patch('src.shared_utils.edo_hooks.get_tools') as mock_get_tools:
        mock_get_tools.return_value = [mock_get_memory_tool]
        
        mock_config = RunnableConfig(configurable={"thread_id": "test_thread"})
        
        # Call bound function with only state and config
        await bound_loader(state={}, config=mock_config)
        
        # Verify agent_id was bound correctly
        call_args = mock_get_memory_tool.ainvoke.call_args[0][0]
        assert "edo_layered_agent" in call_args["metadata_filters"]


if __name__ == "__main__":
    asyncio.run(test_partial_binding_integration())