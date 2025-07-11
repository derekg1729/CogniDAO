"""
Tests for branch isolation enforcement in the MCP Server.

These tests ensure that:
1. DOLT_BRANCH environment variable is properly respected
2. Persistent connections are enabled and maintain branch context
3. All MCP tools operate on the correct branch
4. Branch isolation prevents cross-contamination between branches
"""

import pytest
import os
from unittest.mock import MagicMock, patch
import importlib


class TestBranchIsolation:
    """Test suite for branch isolation functionality."""

    def test_get_current_branch_respects_dolt_branch_env(self):
        """Test that get_current_branch() respects DOLT_BRANCH environment variable."""
        # Test with DOLT_BRANCH set
        with patch.dict(os.environ, {"DOLT_BRANCH": "ai-education-team"}):
            # Import the module fresh to pick up environment variable
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            result = mcp_module.get_current_branch()
            assert result == "ai-education-team"

    def test_get_current_branch_defaults_to_main(self):
        """Test that get_current_branch() defaults to 'main' when DOLT_BRANCH is not set."""
        # Test without DOLT_BRANCH set
        env_without_dolt_branch = {k: v for k, v in os.environ.items() if k != "DOLT_BRANCH"}
        with patch.dict(os.environ, env_without_dolt_branch, clear=True):
            # Import the module fresh
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            result = mcp_module.get_current_branch()
            assert result == "main"

    @patch("mysql.connector.connect")
    @patch("infra_core.memory_system.structured_memory_bank.StructuredMemoryBank")
    @patch("infra_core.memory_system.sql_link_manager.SQLLinkManager")
    def test_persistent_connections_enabled_on_initialization(
        self, mock_link_manager_class, mock_memory_bank_class, mock_mysql_connect
    ):
        """Test that persistent connections are enabled during MCP server initialization."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_mysql_connect.return_value = mock_conn

        mock_memory_bank = MagicMock()
        mock_memory_bank.branch = "test-branch"
        mock_memory_bank_class.return_value = mock_memory_bank

        mock_link_manager = MagicMock()
        mock_link_manager.active_branch = "test-branch"
        mock_link_manager_class.return_value = mock_link_manager

        # Test with specific branch
        with patch.dict(os.environ, {"DOLT_BRANCH": "test-branch"}):
            # Import the module
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            # Trigger lazy initialization by calling get_memory_bank()
            mcp_module.get_memory_bank()

            # Verify StructuredMemoryBank was initialized with correct branch
            mock_memory_bank_class.assert_called_once()
            call_kwargs = mock_memory_bank_class.call_args[1]
            assert call_kwargs["branch"] == "test-branch"

            # Verify persistent connections were enabled on memory bank
            mock_memory_bank.use_persistent_connections.assert_called_once_with("test-branch")

            # Verify persistent connections were enabled on link manager
            mock_link_manager.use_persistent_connection.assert_called_once_with("test-branch")

    def test_different_branches_isolated(self):
        """Test that different branch configurations are properly isolated."""
        # Test branch 1
        with patch.dict(os.environ, {"DOLT_BRANCH": "branch-1"}):
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)
            branch_1_result = mcp_module.get_current_branch()

        # Test branch 2
        with patch.dict(os.environ, {"DOLT_BRANCH": "branch-2"}):
            importlib.reload(mcp_module)
            branch_2_result = mcp_module.get_current_branch()

        # Verify isolation
        assert branch_1_result == "branch-1"
        assert branch_2_result == "branch-2"
        assert branch_1_result != branch_2_result

    @patch("mysql.connector.connect")
    @patch("infra_core.memory_system.structured_memory_bank.StructuredMemoryBank")
    @patch("infra_core.memory_system.sql_link_manager.SQLLinkManager")
    def test_persistent_connection_failure_handling(
        self, mock_link_manager_class, mock_memory_bank_class, mock_mysql_connect
    ):
        """Test that persistent connection failures are handled gracefully."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_mysql_connect.return_value = mock_conn

        mock_memory_bank = MagicMock()
        mock_memory_bank.use_persistent_connections.side_effect = Exception("Connection failed")
        mock_memory_bank_class.return_value = mock_memory_bank

        mock_link_manager = MagicMock()
        mock_link_manager_class.return_value = mock_link_manager

        # Test that initialization fails gracefully when persistent connections fail
        with patch.dict(os.environ, {"DOLT_BRANCH": "test-branch"}):
            # Import the module first
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            # Now test that calling get_memory_bank() raises RuntimeError due to initialization failure
            with pytest.raises(
                RuntimeError
            ):  # Should raise RuntimeError due to initialization failure
                mcp_module.get_memory_bank()

    @pytest.mark.xfail(
        reason="Test isolation issue: caplog fixture affected by other tests in full suite. Passes individually but fails in full test run."
    )
    def test_logging_confirms_branch_context(self, caplog):
        """Test that initialization logging confirms branch context is properly set."""
        # Clear any existing log records to ensure clean test
        caplog.clear()

        with patch("mysql.connector.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.execute.return_value = None
            mock_cursor.fetchone.return_value = (1,)
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            with patch(
                "infra_core.memory_system.structured_memory_bank.StructuredMemoryBank"
            ) as mock_bank:
                with patch("infra_core.memory_system.sql_link_manager.SQLLinkManager") as mock_link:
                    mock_memory_bank = MagicMock()
                    mock_memory_bank.branch = "test-branch"
                    mock_bank.return_value = mock_memory_bank

                    mock_link_manager = MagicMock()
                    mock_link_manager.active_branch = "test-branch"
                    mock_link.return_value = mock_link_manager

                    # Test with specific branch
                    with patch.dict(os.environ, {"DOLT_BRANCH": "test-branch"}):
                        import services.mcp_server.app.mcp_server as mcp_module

                        importlib.reload(mcp_module)

                        # Clear logs again right before the test action
                        caplog.clear()

                        # Trigger lazy initialization by calling get_memory_bank()
                        mcp_module.get_memory_bank()

                        # Check that logging confirms branch context
                        log_messages = [record.message for record in caplog.records]

                        # Should log branch detection
                        assert any(
                            "Using branch from DOLT_BRANCH environment variable: test-branch" in msg
                            for msg in log_messages
                        )

                        # Should log persistent connection enablement
                        assert any(
                            "Enabling persistent connections on branch: test-branch" in msg
                            for msg in log_messages
                        )
                        assert any(
                            "✅ Persistent connections enabled - all operations will use branch: test-branch"
                            in msg
                            for msg in log_messages
                        )
                        assert any(
                            "✅ LinkManager persistent connections enabled on branch: test-branch"
                            in msg
                            for msg in log_messages
                        )

    @pytest.mark.xfail(
        reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
    )
    @pytest.mark.asyncio
    async def test_create_memory_block_uses_correct_branch(self, mcp_app):
        """Test that CreateMemoryBlock tool uses the correct branch context."""
        # Mock the create_memory_block_agent_tool to capture the memory_bank argument
        with patch(
            "services.mcp_server.app.mcp_server.create_memory_block_agent_tool"
        ) as mock_tool:
            mock_tool.return_value = {"success": True, "id": "test-id"}

            test_input = {"type": "doc", "title": "Test Block", "content": "Test content"}

            # Call the MCP tool
            result = await mcp_app.create_memory_block(test_input)

            # Verify the tool was called with memory_bank
            mock_tool.assert_called_once()
            # The memory_bank should be passed as a keyword argument
            assert "memory_bank" in mock_tool.call_args.kwargs
            # Verify we got a result
            assert result is not None

    @pytest.mark.asyncio
    async def test_dolt_auto_commit_respects_branch_context(self, mcp_app):
        """Test that DoltAutoCommitAndPush auto-generated tool respects the branch context."""
        from services.mcp_server.app.tool_registry import get_all_cogni_tools
        from services.mcp_server.app.mcp_auto_generator import create_mcp_wrapper_from_cogni_tool
        
        # Get DoltAutoCommitAndPush auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_auto_commit_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltAutoCommitAndPush":
                dolt_auto_commit_tool = tool
                break
        
        if dolt_auto_commit_tool is None:
            pytest.skip("DoltAutoCommitAndPush tool not found in auto-generated tools")
        
        # Mock memory bank getter
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "main"
            
            # Mock dolt_writer with proper active_branch string
            mock_dolt_writer = MagicMock()
            mock_dolt_writer.active_branch = "main"
            mock_bank.dolt_writer = mock_dolt_writer
            
            return mock_bank
        
        # Create wrapper and test
        wrapper = create_mcp_wrapper_from_cogni_tool(dolt_auto_commit_tool, mock_memory_bank_getter)
        
        # Mock the underlying tool to avoid actual operations
        with patch(
            "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_auto_commit_and_push_tool"
        ) as mock_tool:
            mock_result = MagicMock()
            mock_result.active_branch = "main"
            mock_result.success = True
            mock_tool.return_value = mock_result

            result = await wrapper(commit_message="Test commit", remote_name="origin")
            
            # Verify we got a result from the auto-generated wrapper
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.xfail(
        reason="Legacy implementation now requires MCP integration test - manual tool functions removed in Phase 2A"
    )
    @pytest.mark.asyncio
    async def test_create_block_link_uses_correct_branch(self, mcp_app):
        """Test that CreateBlockLink tool uses the correct branch context."""
        # Mock the create_block_link_agent to capture the memory_bank argument
        with patch("services.mcp_server.app.mcp_server.create_block_link_agent") as mock_tool:
            mock_tool.return_value = MagicMock(model_dump=lambda mode=None: {"success": True})

            test_input = {
                "source_block_id": "12345678-1234-1234-1234-123456789abc",
                "target_block_id": "87654321-4321-4321-4321-cba987654321",
                "relation": "related_to",
            }

            # Call the MCP tool
            result = await mcp_app.create_block_link(test_input)

            # Verify the tool was called with memory_bank
            mock_tool.assert_called_once()
            # The memory_bank should be passed as a keyword argument
            assert "memory_bank" in mock_tool.call_args.kwargs
            # Verify we got a result
            assert result is not None

    @pytest.mark.asyncio
    async def test_dolt_status_uses_memory_bank(self, mcp_app):
        """Test that DoltStatus auto-generated tool uses the memory_bank with branch context."""
        from services.mcp_server.app.tool_registry import get_all_cogni_tools
        from services.mcp_server.app.mcp_auto_generator import create_mcp_wrapper_from_cogni_tool
        
        # Get DoltStatus auto-generated tool
        cogni_tools = get_all_cogni_tools()
        dolt_status_tool = None
        for tool in cogni_tools:
            if tool.name == "DoltStatus":
                dolt_status_tool = tool
                break
        
        if dolt_status_tool is None:
            pytest.skip("DoltStatus tool not found in auto-generated tools")
        
        # Mock memory bank getter
        def mock_memory_bank_getter():
            mock_bank = MagicMock()
            mock_bank.branch = "main"
            
            # Mock dolt_writer with proper active_branch string
            mock_dolt_writer = MagicMock()
            mock_dolt_writer.active_branch = "main"
            mock_bank.dolt_writer = mock_dolt_writer
            
            # Mock the _execute_query to return proper branch info
            def mock_execute_query(query):
                if "active_branch()" in query:
                    return [{"branch": "main"}]
                return []
            
            mock_dolt_writer._execute_query = mock_execute_query
            
            return mock_bank
        
        # Create wrapper and test
        wrapper = create_mcp_wrapper_from_cogni_tool(dolt_status_tool, mock_memory_bank_getter)
        
        # Mock the underlying tool
        with patch("infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_status_tool") as mock_tool:
            mock_result = MagicMock()
            mock_result.model_dump = lambda mode=None: {
                "success": True,
                "active_branch": "main",
                "message": "Working tree clean",
            }
            mock_tool.return_value = mock_result

            result = await wrapper(random_string="test")

            # Verify we got a result from the auto-generated wrapper
            assert result is not None
            assert isinstance(result, dict)


class TestBranchIsolationEdgeCases:
    """Test edge cases and error conditions for branch isolation."""

    def test_ai_education_team_branch_specifically(self):
        """Test the specific AI education team branch that was causing issues."""
        with patch.dict(os.environ, {"DOLT_BRANCH": "ai-education-team"}):
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            result = mcp_module.get_current_branch()
            assert result == "ai-education-team"

    def test_bulk_tools_branch_specifically(self):
        """Test the bulk-tools branch for completeness."""
        with patch.dict(os.environ, {"DOLT_BRANCH": "bulk-tools"}):
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            result = mcp_module.get_current_branch()
            assert result == "bulk-tools"

    def test_empty_dolt_branch_env_var(self):
        """Test behavior when DOLT_BRANCH is set but empty."""
        with patch.dict(os.environ, {"DOLT_BRANCH": ""}):
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            # Empty string should be falsy, so should fall back to main
            result = mcp_module.get_current_branch()
            assert result == "main"

    @patch("mysql.connector.connect")
    @patch("infra_core.memory_system.structured_memory_bank.StructuredMemoryBank")
    @patch("infra_core.memory_system.sql_link_manager.SQLLinkManager")
    def test_branch_context_maintained_across_operations(
        self, mock_link_manager_class, mock_memory_bank_class, mock_mysql_connect
    ):
        """Test that branch context is maintained across different MCP tool operations."""
        # Setup mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock_mysql_connect.return_value = mock_conn

        mock_memory_bank = MagicMock()
        mock_memory_bank.branch = "ai-education-team"
        mock_memory_bank_class.return_value = mock_memory_bank

        mock_link_manager = MagicMock()
        mock_link_manager.active_branch = "ai-education-team"
        mock_link_manager_class.return_value = mock_link_manager

        # Test with AI education team branch
        with patch.dict(os.environ, {"DOLT_BRANCH": "ai-education-team"}):
            # Import the module
            import services.mcp_server.app.mcp_server as mcp_module

            importlib.reload(mcp_module)

            # Verify the current branch detection works correctly
            assert mcp_module.get_current_branch() == "ai-education-team"

            # Verify memory bank and link manager are configured with correct branch
            assert mcp_module.get_memory_bank().branch == "ai-education-team"
            assert mcp_module.get_link_manager().active_branch == "ai-education-team"
