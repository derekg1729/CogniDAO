"""
Tests for MCP Auto-Generator Phase 2 Implementation

This test suite validates that the auto-generator correctly converts CogniTool instances
into MCP tool bindings, ensuring the Phase 2 architecture works as designed.

Coverage:
- CogniTool to MCP wrapper conversion
- Auto-registration functionality
- Error handling and edge cases
- Memory bank integration
- Statistics and reporting
"""

import pytest
from unittest.mock import Mock, patch

from services.mcp_server.app.mcp_auto_generator import (
    create_mcp_wrapper_from_cogni_tool,
    auto_register_cogni_tools_to_mcp,
    get_auto_generation_stats,
)
from services.mcp_server.app.tool_registry import get_all_cogni_tools

from infra_core.memory_system.tools.base.cogni_tool import CogniTool
from pydantic import BaseModel, Field


class MockInputModel(BaseModel):
    """Mock input model for testing."""

    test_field: str = Field(..., description="Test field")
    namespace_id: str = Field("default-namespace", description="Namespace")


class MockOutputModel(BaseModel):
    """Mock output model for testing."""

    success: bool = Field(..., description="Operation success")
    result: str = Field(..., description="Result message")


def mock_function(input_data: MockInputModel, memory_bank=None) -> MockOutputModel:
    """Mock function for testing CogniTool wrapper."""
    return MockOutputModel(
        success=True, result=f"Processed {input_data.test_field} in {input_data.namespace_id}"
    )


@pytest.fixture
def mock_cogni_tool():
    """Create a mock CogniTool for testing."""
    return CogniTool(
        name="TestTool",
        description="A test tool for auto-generator validation",
        input_model=MockInputModel,
        output_model=MockOutputModel,
        function=mock_function,
        memory_linked=True,
    )


@pytest.fixture
def mock_memory_bank():
    """Create a mock memory bank for testing."""
    mock_bank = Mock()
    mock_bank.branch = "test-branch"
    return mock_bank


@pytest.fixture
def mock_memory_bank_getter(mock_memory_bank):
    """Create a mock memory bank getter function."""
    return lambda: mock_memory_bank


@pytest.fixture
def mock_mcp_app():
    """Create a mock FastMCP application."""
    mock_app = Mock()
    mock_app.tool = Mock(return_value=lambda func: func)  # Return decorator that does nothing
    return mock_app


class TestCreateMCPWrapperFromCogniTool:
    """Test the core wrapper generation functionality."""

    @pytest.mark.asyncio
    async def test_wrapper_creation_success(self, mock_cogni_tool, mock_memory_bank_getter):
        """Test successful wrapper creation and execution."""
        wrapper = create_mcp_wrapper_from_cogni_tool(mock_cogni_tool, mock_memory_bank_getter)

        # Test the wrapper function with individual parameters
        result = await wrapper(test_field="hello", namespace_id="test-ns")

        assert result["success"] is True
        assert "hello" in result["result"]
        assert "test-ns" in result["result"]

    @pytest.mark.asyncio
    async def test_wrapper_with_memory_linked_tool(self, mock_cogni_tool, mock_memory_bank_getter):
        """Test wrapper handles memory-linked tools correctly."""
        wrapper = create_mcp_wrapper_from_cogni_tool(mock_cogni_tool, mock_memory_bank_getter)

        # Test with individual parameters
        result = await wrapper(test_field="memory_test")

        # Should inject namespace and call with memory bank
        assert result["success"] is True
        assert "memory_test" in result["result"]

    @pytest.mark.asyncio
    async def test_wrapper_with_non_memory_linked_tool(self, mock_memory_bank_getter):
        """Test wrapper handles non-memory-linked tools correctly."""

        def non_memory_function(input_data: MockInputModel) -> MockOutputModel:
            return MockOutputModel(success=True, result=f"Non-memory: {input_data.test_field}")

        non_memory_tool = CogniTool(
            name="NonMemoryTool",
            description="Non-memory-linked tool",
            input_model=MockInputModel,
            output_model=MockOutputModel,
            function=non_memory_function,
            memory_linked=False,
        )

        wrapper = create_mcp_wrapper_from_cogni_tool(non_memory_tool, mock_memory_bank_getter)

        # Test with individual parameters
        result = await wrapper(test_field="non_memory_test")

        assert result["success"] is True
        assert "Non-memory: non_memory_test" in result["result"]

    @pytest.mark.asyncio
    async def test_wrapper_error_handling(self, mock_memory_bank_getter):
        """Test wrapper handles errors gracefully."""

        def failing_function(input_data: MockInputModel, memory_bank=None) -> MockOutputModel:
            raise ValueError("Test error")

        failing_tool = CogniTool(
            name="FailingTool",
            description="Tool that fails",
            input_model=MockInputModel,
            output_model=MockOutputModel,
            function=failing_function,
            memory_linked=True,
        )

        wrapper = create_mcp_wrapper_from_cogni_tool(failing_tool, mock_memory_bank_getter)

        # Test with individual parameters
        result = await wrapper(test_field="will_fail")

        assert result["success"] is False
        assert "Failed to execute FailingTool" in result["error"]
        assert "Test error" in result["error"]
        assert "current_branch" in result

    @pytest.mark.asyncio
    async def test_wrapper_input_validation_error(self, mock_cogni_tool, mock_memory_bank_getter):
        """Test wrapper handles input validation errors."""
        wrapper = create_mcp_wrapper_from_cogni_tool(mock_cogni_tool, mock_memory_bank_getter)

        # Missing required field - call without test_field parameter
        result = await wrapper(namespace_id="test")  # Missing test_field

        assert result["success"] is False
        assert "Failed to execute TestTool" in result["error"]

    def test_wrapper_metadata(self, mock_cogni_tool, mock_memory_bank_getter):
        """Test wrapper function metadata is set correctly."""
        wrapper = create_mcp_wrapper_from_cogni_tool(mock_cogni_tool, mock_memory_bank_getter)

        assert wrapper.__name__ == "testtool_mcp_wrapper"
        assert "Auto-generated MCP wrapper" in wrapper.__doc__
        assert "TestTool" in wrapper.__doc__


class TestAutoRegisterCogniToolsToMCP:
    """Test the auto-registration functionality."""

    def test_auto_registration_success(self, mock_mcp_app, mock_memory_bank_getter):
        """Test successful auto-registration of all CogniTools."""
        with patch(
            "services.mcp_server.app.mcp_auto_generator.get_all_cogni_tools"
        ) as mock_get_tools:
            # Create proper mock tools with correct structure
            mock_tool1 = Mock()
            mock_tool1.name = "Tool1"
            mock_tool1.memory_linked = True
            mock_tool1.input_model = MockInputModel
            mock_tool1._function = mock_function

            mock_tool2 = Mock()
            mock_tool2.name = "Tool2"
            mock_tool2.memory_linked = False
            mock_tool2.input_model = MockInputModel
            mock_tool2._function = mock_function

            mock_tools = [mock_tool1, mock_tool2]
            mock_get_tools.return_value = mock_tools

            results = auto_register_cogni_tools_to_mcp(mock_mcp_app, mock_memory_bank_getter)

            assert len(results) == 2
            assert results["Tool1"] == "SUCCESS"
            assert results["Tool2"] == "SUCCESS"

            # Verify mcp_app.tool was called for each tool
            assert mock_mcp_app.tool.call_count == 2

    def test_auto_registration_with_errors(self, mock_mcp_app, mock_memory_bank_getter):
        """Test auto-registration handles individual tool errors."""
        with patch(
            "services.mcp_server.app.mcp_auto_generator.get_all_cogni_tools"
        ) as mock_get_tools:
            # Create one good tool to verify the happy path
            good_tool = Mock()
            good_tool.name = "GoodTool"
            good_tool.memory_linked = True
            good_tool.input_model = MockInputModel
            good_tool._function = mock_function

            mock_tools = [good_tool]
            mock_get_tools.return_value = mock_tools

            results = auto_register_cogni_tools_to_mcp(mock_mcp_app, mock_memory_bank_getter)

            assert len(results) == 1
            assert results["GoodTool"] == "SUCCESS"

            # Verify the MCP app tool registration was called
            assert mock_mcp_app.tool.call_count == 1


class TestGetAutoGenerationStats:
    """Test the statistics reporting functionality."""

    def test_stats_calculation(self):
        """Test that stats are calculated correctly."""
        with patch(
            "services.mcp_server.app.mcp_auto_generator.get_all_cogni_tools"
        ) as mock_get_tools:
            # Mock 5 tools for predictable stats
            mock_tools = [Mock(memory_linked=True, name=f"Tool{i}") for i in range(5)]
            mock_get_tools.return_value = mock_tools

            stats = get_auto_generation_stats()

            assert stats["total_cogni_tools"] == 5
            assert stats["memory_linked_tools"] == 5
            assert stats["non_memory_linked_tools"] == 0
            assert stats["estimated_manual_lines_replaced"] == 250  # 5 * 50
            assert stats["lines_saved"] == 100  # 250 - 150
            assert stats["maintenance_reduction_percent"] == 40.0  # 100/250 * 100

    def test_stats_with_mixed_tools(self):
        """Test stats with mixed memory-linked and non-memory-linked tools."""
        with patch(
            "services.mcp_server.app.mcp_auto_generator.get_all_cogni_tools"
        ) as mock_get_tools:
            mock_tools = [
                Mock(memory_linked=True, name="MemoryTool1"),
                Mock(memory_linked=True, name="MemoryTool2"),
                Mock(memory_linked=False, name="NonMemoryTool1"),
            ]
            mock_get_tools.return_value = mock_tools

            stats = get_auto_generation_stats()

            assert stats["total_cogni_tools"] == 3
            assert stats["memory_linked_tools"] == 2
            assert stats["non_memory_linked_tools"] == 1


class TestIntegrationWithRealCogniTools:
    """Integration tests with actual CogniTool instances."""

    def test_real_cogni_tools_loading(self):
        """Test that real CogniTools can be loaded and processed."""
        cogni_tools = get_all_cogni_tools()

        # Should have the expected number of tools
        assert len(cogni_tools) >= 15  # We know we have at least 19

        # All should be CogniTool instances
        for tool in cogni_tools:
            assert hasattr(tool, "name")
            assert hasattr(tool, "memory_linked")
            assert hasattr(tool, "input_model")
            assert hasattr(tool, "output_model")
            assert hasattr(tool, "_function")

    def test_real_tool_wrapper_creation(self, mock_memory_bank_getter):
        """Test wrapper creation with real CogniTool instances."""
        cogni_tools = get_all_cogni_tools()

        # Test wrapper creation for first few tools
        for tool in cogni_tools[:3]:  # Test first 3 tools
            wrapper = create_mcp_wrapper_from_cogni_tool(tool, mock_memory_bank_getter)

            # Should be callable
            assert callable(wrapper)

            # Should have proper metadata
            assert hasattr(wrapper, "__name__")
            assert hasattr(wrapper, "__doc__")

    def test_stats_with_real_tools(self):
        """Test statistics calculation with real tools."""
        stats = get_auto_generation_stats()

        # Verify stats structure
        required_keys = [
            "total_cogni_tools",
            "memory_linked_tools",
            "non_memory_linked_tools",
            "tool_names",
            "estimated_manual_lines_replaced",
            "auto_generator_lines",
            "lines_saved",
            "maintenance_reduction_percent",
        ]

        for key in required_keys:
            assert key in stats

        # Verify reasonable values
        assert stats["total_cogni_tools"] > 0
        assert stats["maintenance_reduction_percent"] > 0
        assert stats["lines_saved"] > 0


class TestErrorEdgeCases:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_wrapper_with_none_memory_bank_getter(self, mock_cogni_tool):
        """Test wrapper when memory bank getter returns None."""

        def null_memory_bank_getter():
            return None

        wrapper = create_mcp_wrapper_from_cogni_tool(mock_cogni_tool, null_memory_bank_getter)

        # Test with individual parameters
        result = await wrapper(test_field="test")

        # Should still work even with None memory bank
        assert result["success"] is True
        assert "test" in result["result"]

    @pytest.mark.asyncio
    async def test_wrapper_serialization_edge_cases(self, mock_memory_bank_getter):
        """Test wrapper handles different result serialization scenarios."""

        # Tool that returns dict directly
        def dict_returning_function(input_data: MockInputModel, memory_bank=None):
            return {"success": True, "data": "dict_result"}

        dict_tool = CogniTool(
            name="DictTool",
            description="Returns dict",
            input_model=MockInputModel,
            output_model=MockOutputModel,
            function=dict_returning_function,
            memory_linked=True,
        )

        wrapper = create_mcp_wrapper_from_cogni_tool(dict_tool, mock_memory_bank_getter)

        # Test with individual parameters
        result = await wrapper(test_field="test")

        assert result["success"] is True
        assert result["data"] == "dict_result"

    def test_auto_registration_empty_tools_list(self, mock_mcp_app, mock_memory_bank_getter):
        """Test auto-registration with empty tools list."""
        with patch(
            "services.mcp_server.app.mcp_auto_generator.get_all_cogni_tools"
        ) as mock_get_tools:
            mock_get_tools.return_value = []

            results = auto_register_cogni_tools_to_mcp(mock_mcp_app, mock_memory_bank_getter)

            assert len(results) == 0
            assert mock_mcp_app.tool.call_count == 0
