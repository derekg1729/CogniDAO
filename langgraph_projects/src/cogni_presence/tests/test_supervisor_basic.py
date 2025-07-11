"""
Basic tests for the supervisor pattern.
Tests that the graph compiles and has the expected structure.
"""

import pytest
from unittest.mock import patch, AsyncMock

from src.cogni_presence.graph import build_graph, build_compiled_graph


class TestSupervisorBasic:
    """Basic tests for supervisor pattern functionality."""

    @pytest.mark.asyncio
    async def test_supervisor_graph_compiles(self):
        """Test that the supervisor graph compiles without errors."""
        # Mock MCP tools to avoid connection issues in tests
        mock_tools = []
        
        with patch('src.shared_utils.tool_registry.get_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_get_tools.return_value = mock_tools
            
            # This should not raise an exception
            graph = await build_graph()
            assert graph is not None
            
            # Compile the graph
            compiled_graph = await build_compiled_graph()
            assert compiled_graph is not None

    @pytest.mark.asyncio 
    async def test_supervisor_has_expected_structure(self):
        """Test that the supervisor has the expected agents."""
        mock_tools = []
        
        with patch('src.shared_utils.tool_registry.get_tools', new_callable=AsyncMock) as mock_get_tools:
            mock_get_tools.return_value = mock_tools
            
            compiled_graph = await build_compiled_graph()
            
            # The compiled supervisor should have the expected structure
            # Note: We can't easily inspect the internal structure of create_supervisor
            # but we can verify it compiles and is the right type
            assert hasattr(compiled_graph, 'invoke')
            assert hasattr(compiled_graph, 'ainvoke')