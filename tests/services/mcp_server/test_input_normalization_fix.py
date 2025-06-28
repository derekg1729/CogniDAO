"""
Tests for MCP input normalization fix.

This test file validates that the _normalize_mcp_input function correctly handles:
1. Double-serialization scenarios (dict -> JSON string -> escaped JSON string)
2. Valid dict input (pass-through)
3. Simple JSON string input
4. Invalid input types (graceful failure)
5. Edge cases (empty strings, malformed JSON, etc.)

The fix addresses the critical issue where autogen agents double-serialize inputs:
dict -> JSON string -> escaped string, causing Pydantic validation failures.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from services.mcp_server.app.mcp_server import (
    _normalize_mcp_input,
    inject_current_namespace,
    create_work_item,
    get_memory_block,
    query_memory_blocks_semantic,
)


class TestNormalizeMCPInput:
    """Test class for the _normalize_mcp_input function."""

    def test_normalize_valid_dict_passthrough(self):
        """Test that valid dictionaries pass through unchanged."""
        test_dict = {"type": "task", "title": "Test Task", "namespace_id": "test-ns"}
        result = _normalize_mcp_input(test_dict)
        assert result == test_dict
        assert isinstance(result, dict)

    def test_normalize_simple_json_string(self):
        """Test that simple JSON strings are properly parsed."""
        test_dict = {"type": "task", "title": "Test Task"}
        json_string = json.dumps(test_dict)
        result = _normalize_mcp_input(json_string)
        assert result == test_dict
        assert isinstance(result, dict)

    def test_normalize_double_serialized_json(self):
        """Test that double-serialized JSON is properly handled."""
        original_dict = {"type": "task", "title": "Test Task", "priority": "P1"}

        # Simulate double serialization: dict -> JSON -> JSON again
        first_json = json.dumps(original_dict)
        double_json = json.dumps(first_json)

        result = _normalize_mcp_input(double_json)
        assert result == original_dict
        assert isinstance(result, dict)

    def test_normalize_triple_serialized_json(self):
        """Test that even triple-serialized JSON is handled (edge case)."""
        original_dict = {"type": "project", "title": "Test Project"}

        # Simulate triple serialization: dict -> JSON -> JSON -> JSON
        first_json = json.dumps(original_dict)
        second_json = json.dumps(first_json)
        triple_json = json.dumps(second_json)

        result = _normalize_mcp_input(triple_json)
        assert result == original_dict
        assert isinstance(result, dict)

    def test_normalize_complex_data_types(self):
        """Test normalization with complex data types (lists, nested objects)."""
        complex_dict = {
            "type": "epic",
            "title": "Complex Epic",
            "tags": ["backend", "api", "critical"],
            "metadata": {
                "priority": "P0",
                "team": "core",
                "nested": {"key": "value", "number": 42},
            },
            "acceptance_criteria": [
                "Implement API endpoint",
                "Add comprehensive tests",
                "Update documentation",
            ],
        }

        # Test with double serialization of complex data
        json_string = json.dumps(complex_dict)
        double_json = json.dumps(json_string)

        result = _normalize_mcp_input(double_json)
        assert result == complex_dict
        assert isinstance(result, dict)
        assert result["tags"] == ["backend", "api", "critical"]
        assert result["metadata"]["nested"]["number"] == 42

    def test_normalize_empty_dict(self):
        """Test that empty dictionaries are handled correctly."""
        result = _normalize_mcp_input({})
        assert result == {}
        assert isinstance(result, dict)

    def test_normalize_empty_string_fails(self):
        """Test that empty strings fail gracefully with descriptive error."""
        with pytest.raises(ValueError) as exc_info:
            _normalize_mcp_input("")

        assert "Invalid JSON input" in str(exc_info.value)
        assert "Expecting value" in str(exc_info.value)

    def test_normalize_invalid_json_fails(self):
        """Test that malformed JSON strings fail gracefully."""
        malformed_json = '{"type": "task", "title": "Unclosed'

        with pytest.raises(ValueError) as exc_info:
            _normalize_mcp_input(malformed_json)

        assert "Invalid JSON input" in str(exc_info.value)

    def test_normalize_non_string_non_dict_fails(self):
        """Test that invalid input types fail gracefully."""
        invalid_inputs = [123, [], None, True, set([1, 2, 3])]

        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError) as exc_info:
                _normalize_mcp_input(invalid_input)

            assert "MCP input must be dict or JSON string" in str(exc_info.value)

    def test_normalize_unicode_handling(self):
        """Test that Unicode characters are properly handled."""
        unicode_dict = {
            "type": "task",
            "title": "Unicode Test: 测试 🚀 émojis",
            "description": "Ñoño piñata jalapeño",
        }

        json_string = json.dumps(unicode_dict, ensure_ascii=False)
        double_json = json.dumps(json_string, ensure_ascii=False)

        result = _normalize_mcp_input(double_json)
        assert result == unicode_dict
        assert result["title"] == "Unicode Test: 测试 🚀 émojis"

    def test_normalize_large_payload(self):
        """Test normalization with larger payloads."""
        large_dict = {
            "type": "doc",
            "title": "Large Document",
            "content": "x" * 10000,  # 10KB of text
            "metadata": {f"key_{i}": f"value_{i}" for i in range(100)},
        }

        json_string = json.dumps(large_dict)
        result = _normalize_mcp_input(json_string)
        assert result == large_dict
        assert len(result["content"]) == 10000
        assert len(result["metadata"]) == 100


class TestInputNormalizationIntegration:
    """Integration tests for input normalization with actual MCP tools."""

    @pytest.mark.asyncio
    async def test_create_work_item_with_normalized_input(self):
        """Test that CreateWorkItem properly normalizes double-serialized input."""
        with patch("services.mcp_server.app.mcp_server.create_work_item_tool") as mock_tool:
            mock_tool.return_value = {
                "success": True,
                "id": "test-work-item-123",
                "work_item_type": "task",
            }

            # Simulate double-serialized input from autogen with all required fields
            original_input = {
                "type": "task",
                "title": "Test Task",
                "description": "Test description",
                "acceptance_criteria": ["Task must be completed"],  # Required field
            }
            json_input = json.dumps(original_input)
            double_json_input = json.dumps(json_input)

            await create_work_item(double_json_input)

            # Verify the tool was called with normalized input
            mock_tool.assert_called_once()
            call_args = mock_tool.call_args[0][0]  # First positional argument
            assert call_args.type == "task"
            assert call_args.title == "Test Task"
            assert call_args.description == "Test description"
            assert call_args.acceptance_criteria == ["Task must be completed"]

    @pytest.mark.asyncio
    async def test_query_semantic_with_escaped_json(self):
        """Test that QueryMemoryBlocksSemantic handles escaped JSON properly."""
        with (
            patch("services.mcp_server.app.mcp_server.query_memory_blocks_core") as mock_tool,
            patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank,
        ):
            mock_tool.return_value = MagicMock()
            mock_tool.return_value.model_dump.return_value = {
                "success": True,
                "blocks": [],
                "message": "Query completed",
            }

            # Mock the memory bank to avoid database connection issues
            mock_memory_bank = MagicMock()
            mock_bank.return_value = mock_memory_bank

            # Simulate escaped JSON that might come from agents
            original_input = {
                "query_text": "Find tasks with priority P0",
                "type_filter": "task",
                "top_k": 5,
            }
            escaped_json = json.dumps(json.dumps(original_input))

            await query_memory_blocks_semantic(escaped_json)

            # Verify the core function was called with properly parsed input
            mock_tool.assert_called_once()
            call_args = mock_tool.call_args[0][0]  # First positional argument
            assert call_args.query_text == "Find tasks with priority P0"
            assert call_args.type_filter == "task"
            assert call_args.top_k == 5


class TestNamespaceInjectionWithNormalization:
    """Test that namespace injection works correctly with input normalization."""

    def test_inject_namespace_with_normalized_dict(self):
        """Test that namespace injection works after input normalization."""
        with (
            patch("services.mcp_server.app.mcp_server.get_current_namespace") as mock_ns,
            patch("services.mcp_server.app.mcp_server._current_namespace", "test-namespace"),
        ):
            mock_ns.return_value = "test-namespace"

            # Test with double-serialized input that lacks namespace_id
            original_input = {"type": "task", "title": "Test Task"}
            json_input = json.dumps(original_input)
            double_json = json.dumps(json_input)

            result = inject_current_namespace(double_json)

            assert result["namespace_id"] == "test-namespace"
            assert result["type"] == "task"
            assert result["title"] == "Test Task"

    def test_inject_namespace_preserves_explicit_namespace(self):
        """Test that explicit namespace in normalized input is preserved."""
        with patch("services.mcp_server.app.mcp_server.get_current_namespace") as mock_ns:
            mock_ns.return_value = "default-namespace"

            # Test with explicit namespace_id in double-serialized input
            original_input = {
                "type": "project",
                "title": "Test Project",
                "namespace_id": "custom-namespace",
            }
            double_json = json.dumps(json.dumps(original_input))

            result = inject_current_namespace(double_json)

            # Should preserve the explicit namespace, not inject default
            assert result["namespace_id"] == "custom-namespace"
            assert result["type"] == "project"

    def test_inject_namespace_handles_normalization_failure(self):
        """Test that namespace injection fails gracefully when normalization fails."""
        with patch("services.mcp_server.app.mcp_server.get_current_namespace") as mock_ns:
            mock_ns.return_value = "test-namespace"

            # Invalid input that should fail normalization
            invalid_input = "malformed json {"

            with pytest.raises(ValueError):
                inject_current_namespace(invalid_input)


class TestErrorHandlingWithNormalization:
    """Test error handling scenarios with input normalization."""

    @pytest.mark.asyncio
    async def test_mcp_tool_handles_normalization_errors_gracefully(self):
        """Test that MCP tools handle normalization errors gracefully."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()

            # Pass invalid input that should fail normalization
            invalid_input = 12345  # Not a dict or string

            result = await create_work_item(invalid_input)

            # Should return error response instead of crashing
            assert isinstance(result, dict)
            assert "error" in result
            assert "MCP input must be dict or JSON string" in result["error"]

    @pytest.mark.asyncio
    async def test_partial_normalization_recovery(self):
        """Test that tools can recover from partial normalization failures."""
        with patch("services.mcp_server.app.mcp_server.get_memory_bank") as mock_bank:
            mock_bank.return_value = MagicMock()
            mock_bank.return_value.get_all_memory_blocks.return_value = []

            # JSON string with valid structure but missing required fields
            partial_input = json.dumps({"some_field": "some_value"})

            result = await get_memory_block(partial_input)

            # Should handle the normalization but fail validation gracefully
            assert isinstance(result, dict)
            # The exact error depends on validation logic, but it shouldn't crash


class TestPerformanceWithNormalization:
    """Test performance implications of input normalization."""

    def test_normalization_performance_with_large_inputs(self):
        """Test that normalization doesn't significantly impact performance."""
        import time

        # Create a reasonably large input
        large_input = {
            "type": "doc",
            "title": "Large Document",
            "content": "Lorem ipsum " * 1000,  # ~11KB
            "metadata": {f"field_{i}": f"value_{i}" for i in range(200)},
        }

        # Test direct dict (baseline) - run multiple times for better measurement
        dict_times = []
        for _ in range(100):
            start_time = time.time()
            result1 = _normalize_mcp_input(large_input)
            dict_times.append(time.time() - start_time)
        dict_time = sum(dict_times) / len(dict_times)

        # Test double-serialized JSON - run multiple times for better measurement
        double_json = json.dumps(json.dumps(large_input))
        json_times = []
        for _ in range(100):
            start_time = time.time()
            result2 = _normalize_mcp_input(double_json)
            json_times.append(time.time() - start_time)
        json_time = sum(json_times) / len(json_times)

        # Verify results are equivalent
        assert result1 == result2 == large_input

        # Normalization overhead should be reasonable
        # If dict_time is too small to measure accurately, just ensure JSON parsing works
        if dict_time > 0:
            overhead_ratio = json_time / dict_time
            assert overhead_ratio < 50, (
                f"JSON normalization took {overhead_ratio:.1f}x longer than dict passthrough"
            )
        else:
            # Both operations are too fast to measure - just verify they work
            assert result1 == large_input
            assert result2 == large_input


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
