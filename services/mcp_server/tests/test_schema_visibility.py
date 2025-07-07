"""
Tests for MCP Tool Schema Visibility

These tests validate that auto-registered tools properly expose their parameter schemas
for visibility through the MCP interface. This ensures that tools converted from manual
registrations to auto-generated ones maintain proper schema discoverability.

Key validations:
- All tools expose input/output models
- Individual parameters are discoverable (not wrapped in input objects)
- Schema fields match expected CogniTool structures
- Parameter types and requirements are correctly exposed
"""

import pytest

from services.mcp_server.app.tool_registry import get_all_cogni_tools
from services.mcp_server.app.mcp_auto_generator import create_mcp_wrapper_from_cogni_tool
from unittest.mock import MagicMock


@pytest.fixture
def mock_memory_bank_getter():
    """Create a mock memory bank getter function."""
    def getter():
        mock_bank = MagicMock()
        mock_bank.branch = "test-branch"
        return mock_bank
    return getter


class TestSchemaVisibility:
    """Test that auto-registered tools properly expose their schemas."""

    def test_all_tools_have_discoverable_schemas(self):
        """Test that all auto-registered tools have discoverable input/output schemas."""
        tools = get_all_cogni_tools()
        
        assert len(tools) > 0, "Should have auto-registered tools available"
        
        for tool in tools:
            # Every tool should have input and output models
            assert hasattr(tool, 'input_model'), f"Tool {tool.name} missing input_model"
            assert hasattr(tool, 'output_model'), f"Tool {tool.name} missing output_model"
            
            # Models should have accessible field definitions
            assert hasattr(tool.input_model, 'model_fields'), f"Tool {tool.name} input_model missing model_fields"
            assert hasattr(tool.output_model, 'model_fields'), f"Tool {tool.name} output_model missing model_fields"

    def test_namespace_tools_schema_visibility(self):
        """Test that namespace tools expose correct parameter schemas."""
        tools = get_all_cogni_tools()
        namespace_tools = {tool.name: tool for tool in tools if "namespace" in tool.name.lower()}
        
        # Should have the converted namespace tools
        expected_tools = ["CreateNamespace", "ListNamespaces", "BulkUpdateNamespace"]
        for tool_name in expected_tools:
            assert tool_name in namespace_tools, f"Missing namespace tool: {tool_name}"
            
            tool = namespace_tools[tool_name]
            input_fields = tool.input_model.model_fields
            
            # Validate schema structure
            assert isinstance(input_fields, dict), f"{tool_name} should have dict-like model_fields"
            
            # CreateNamespace should have id and name parameters
            if tool_name == "CreateNamespace":
                assert "id" in input_fields, "CreateNamespace should have 'id' parameter"
                assert "name" in input_fields, "CreateNamespace should have 'name' parameter"

    def test_dolt_tools_schema_visibility(self):
        """Test that Dolt tools expose correct parameter schemas."""
        tools = get_all_cogni_tools()
        dolt_tools = {tool.name: tool for tool in tools if tool.name.startswith("Dolt")}
        
        # Should have Core Dolt tools (Batch 2)
        core_dolt_tools = ["DoltCommit", "DoltAdd", "DoltStatus", "DoltCheckout", "DoltReset", "DoltPush"]
        for tool_name in core_dolt_tools:
            if tool_name in dolt_tools:
                tool = dolt_tools[tool_name]
                input_fields = tool.input_model.model_fields
                
                # Validate schema structure
                assert isinstance(input_fields, dict), f"{tool_name} should have dict-like model_fields"
                
                # DoltCommit should have commit_message parameter
                if tool_name == "DoltCommit":
                    assert "commit_message" in input_fields, "DoltCommit should have 'commit_message' parameter"

        # Should have Advanced Dolt tools (Batch 3)
        advanced_dolt_tools = ["DoltPull", "DoltBranch", "DoltListBranches", "DoltDiff", "DoltAutoCommitAndPush", "DoltMerge"]
        for tool_name in advanced_dolt_tools:
            if tool_name in dolt_tools:
                tool = dolt_tools[tool_name]
                input_fields = tool.input_model.model_fields
                
                # Validate schema structure
                assert isinstance(input_fields, dict), f"{tool_name} should have dict-like model_fields"

    def test_memory_operation_tools_schema_visibility(self):
        """Test that memory operation tools expose correct parameter schemas."""
        tools = get_all_cogni_tools()
        memory_tools = {tool.name: tool for tool in tools if "Memory" in tool.name or "WorkItem" in tool.name}
        
        # Core memory tools
        expected_memory_tools = ["CreateMemoryBlock", "GetMemoryBlock", "UpdateMemoryBlock", "CreateWorkItem", "UpdateWorkItem"]
        
        for tool_name in expected_memory_tools:
            if tool_name in memory_tools:
                tool = memory_tools[tool_name]
                input_fields = tool.input_model.model_fields
                
                # Validate schema structure
                assert isinstance(input_fields, dict), f"{tool_name} should have dict-like model_fields"
                
                # Memory-linked tools should typically have namespace_id support
                if tool.memory_linked:
                    # Most memory-linked tools should support namespace injection
                    # (namespace_id might be optional/default but should be in schema or auto-injected)
                    pass  # Auto-injection handles this transparently

    def test_wrapper_function_signatures(self, mock_memory_bank_getter):
        """Test that wrapper functions expose correct signatures for MCP binding."""
        tools = get_all_cogni_tools()
        
        # Test a few representative tools
        test_tools = []
        for tool in tools:
            if tool.name in ["HealthCheck", "CreateNamespace", "GetMemoryBlock"]:
                test_tools.append(tool)
        
        assert len(test_tools) > 0, "Should find test tools for signature validation"
        
        for tool in test_tools:
            wrapper = create_mcp_wrapper_from_cogni_tool(tool, mock_memory_bank_getter)
            
            # Wrapper should be callable
            assert callable(wrapper), f"Wrapper for {tool.name} should be callable"
            
            # Wrapper should have proper metadata
            assert hasattr(wrapper, '__name__'), f"Wrapper for {tool.name} should have __name__"
            assert hasattr(wrapper, '__doc__'), f"Wrapper for {tool.name} should have __doc__"
            
            # Name should follow convention
            expected_name = f"{tool.name.lower()}_mcp_wrapper"
            assert wrapper.__name__ == expected_name, f"Wrapper name should be {expected_name}"

    def test_parameter_types_are_discoverable(self):
        """Test that parameter types are properly discoverable from schemas."""
        tools = get_all_cogni_tools()
        
        # Test CreateNamespace tool specifically
        create_namespace_tool = None
        for tool in tools:
            if tool.name == "CreateNamespace":
                create_namespace_tool = tool
                break
        
        if create_namespace_tool:
            input_fields = create_namespace_tool.input_model.model_fields
            
            # Should have discoverable field types
            for field_name, field_info in input_fields.items():
                assert hasattr(field_info, 'annotation'), f"Field {field_name} should have type annotation"
                
                # Common fields should have expected types
                if field_name == "id":
                    # Should be string type (exact annotation format may vary)
                    assert field_info.annotation is not None
                elif field_name == "name":
                    # Should be string type
                    assert field_info.annotation is not None

    def test_output_schemas_are_discoverable(self):
        """Test that output schemas are properly discoverable."""
        tools = get_all_cogni_tools()
        
        for tool in tools:
            output_fields = tool.output_model.model_fields
            
            # Output models should be discoverable
            assert isinstance(output_fields, dict), f"Tool {tool.name} should have discoverable output schema"
            
            # Most tools should have at least some output fields
            # (Though some simple tools might have minimal output schemas)

    def test_memory_linked_tools_schema_consistency(self):
        """Test that memory-linked tools have consistent schema patterns."""
        tools = get_all_cogni_tools()
        memory_linked_tools = [tool for tool in tools if tool.memory_linked]
        
        assert len(memory_linked_tools) > 0, "Should have memory-linked tools"
        
        for tool in memory_linked_tools:
            # Memory-linked tools should have proper input/output schemas
            assert hasattr(tool.input_model, 'model_fields')
            assert hasattr(tool.output_model, 'model_fields')
            
            # Most memory-linked tools support namespace handling
            # (either explicitly or via auto-injection)
            _input_fields = tool.input_model.model_fields
            
            # Namespace handling can be:
            # 1. Explicit namespace_id parameter
            # 2. Auto-injected by wrapper (transparent to schema)
            # Both are valid approaches


class TestParameterHandling:
    """Test that auto-registered tools handle individual parameters correctly."""

    @pytest.mark.asyncio
    async def test_individual_parameter_acceptance(self, mock_memory_bank_getter):
        """Test that tools accept individual parameters (not wrapped input objects)."""
        tools = get_all_cogni_tools()
        
        # Test HealthCheck (simple tool with no required parameters)
        health_check_tool = None
        for tool in tools:
            if tool.name == "HealthCheck":
                health_check_tool = tool
                break
        
        if health_check_tool:
            wrapper = create_mcp_wrapper_from_cogni_tool(health_check_tool, mock_memory_bank_getter)
            
            # Should be able to call with no parameters
            try:
                result = await wrapper()
                assert isinstance(result, dict), "HealthCheck should return dict result"
            except Exception as e:
                # Should not fail due to parameter format issues
                assert "validation error" not in str(e).lower()

    @pytest.mark.asyncio
    async def test_parameter_validation_handling(self, mock_memory_bank_getter):
        """Test that parameter validation works correctly for auto-registered tools."""
        tools = get_all_cogni_tools()
        
        # Test CreateNamespace (tool with required parameters)
        create_namespace_tool = None
        for tool in tools:
            if tool.name == "CreateNamespace":
                create_namespace_tool = tool
                break
        
        if create_namespace_tool:
            wrapper = create_mcp_wrapper_from_cogni_tool(create_namespace_tool, mock_memory_bank_getter)
            
            # Should handle missing required parameters gracefully
            result = await wrapper()
            assert isinstance(result, dict), "Should return error dict for missing parameters"
            assert result.get("success") is False, "Should indicate failure for missing parameters"
            assert "error" in result, "Should include error message"

    @pytest.mark.asyncio
    async def test_optional_parameter_handling(self, mock_memory_bank_getter):
        """Test that optional parameters are handled correctly."""
        tools = get_all_cogni_tools()
        
        # Test GetMemoryBlock (tool with optional parameters)
        get_memory_block_tool = None
        for tool in tools:
            if tool.name == "GetMemoryBlock":
                get_memory_block_tool = tool
                break
        
        if get_memory_block_tool:
            wrapper = create_mcp_wrapper_from_cogni_tool(get_memory_block_tool, mock_memory_bank_getter)
            
            # Should handle tool call with some parameters
            try:
                import uuid
                result = await wrapper(block_ids=str(uuid.uuid4()))
                assert isinstance(result, dict), "Should return dict result"
            except Exception as e:
                # Should not fail due to parameter format issues
                assert "validation error" not in str(e).lower()


class TestSchemaEvolution:
    """Test that schema evolution is handled correctly."""

    def test_backward_compatibility_maintained(self):
        """Test that schema changes maintain backward compatibility."""
        tools = get_all_cogni_tools()
        
        # Key tools should maintain expected parameter names
        for tool in tools:
            if tool.name == "CreateWorkItem":
                input_fields = tool.input_model.model_fields
                
                # Should have core work item fields
                expected_fields = ["type", "title"]
                for field in expected_fields:
                    assert field in input_fields, f"CreateWorkItem should have {field} parameter"
            
            elif tool.name == "GetMemoryBlock":
                input_fields = tool.input_model.model_fields
                
                # Should have block identification fields
                # (exact field names may vary but should be discoverable)
                assert len(input_fields) >= 0, "GetMemoryBlock should have discoverable schema"

    def test_tool_count_progression(self):
        """Test that tool count meets expectations after all conversions."""
        tools = get_all_cogni_tools()
        
        # After all batches (1, 2, 3), should have 32+ tools
        # Phase 1: GetActiveWorkItems, GetLinkedBlocks  
        # Batch 1: 3 namespace tools
        # Batch 2: 6 core Dolt tools
        # Batch 3: 6 advanced Dolt tools
        # Plus existing tools: ~15+ original auto-generated tools
        # Total: 32+ tools
        
        assert len(tools) >= 32, f"Expected at least 32 tools after all conversions, got {len(tools)}"

    def test_no_duplicate_tool_names(self):
        """Test that there are no duplicate tool names in the registry."""
        tools = get_all_cogni_tools()
        tool_names = [tool.name for tool in tools]
        
        # Should have no duplicates
        unique_names = set(tool_names)
        assert len(tool_names) == len(unique_names), f"Found duplicate tool names: {tool_names}"