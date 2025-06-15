#!/usr/bin/env python3
"""
Comprehensive tests for branch protection functionality.

Tests that write operations are blocked on protected branches
and allowed on feature branches for both DoltWriter and SQLLinkManager.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig, MainBranchProtectionError
from infra_core.memory_system.dolt_writer import DoltMySQLWriter
from infra_core.memory_system.sql_link_manager import SQLLinkManager
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.relation_registry import PMRelationType


class TestBranchProtectionConfiguration:
    """Test branch protection configuration and environment variables."""

    def test_default_protected_branch_is_main(self):
        """Test that main is the default protected branch."""
        # Clear environment to test defaults
        with patch.dict(os.environ, {}, clear=True):
            # Re-import to get fresh environment
            import importlib
            import infra_core.memory_system.dolt_mysql_base as base_module

            importlib.reload(base_module)

            assert "main" in base_module.PROTECTED_BRANCHES

    def test_custom_protected_branch_from_env(self):
        """Test that protected branches can be configured via environment."""
        with patch.dict(os.environ, {"DOLT_PROTECTED_BRANCH": "production"}):
            import importlib
            import infra_core.memory_system.dolt_mysql_base as base_module

            importlib.reload(base_module)

            assert "production" in base_module.PROTECTED_BRANCHES

    def test_multiple_protected_branches_from_env(self):
        """Test that multiple protected branches can be configured."""
        with patch.dict(os.environ, {"DOLT_PROTECTED_BRANCHES": "main,production,staging"}):
            import importlib
            import infra_core.memory_system.dolt_mysql_base as base_module

            importlib.reload(base_module)

            expected_branches = ["main", "production", "staging"]
            for branch in expected_branches:
                assert branch in base_module.PROTECTED_BRANCHES


class TestDoltWriterBranchProtection:
    """Test branch protection in DoltMySQLWriter."""

    @pytest.fixture
    def mock_writer(self):
        """Create a mocked DoltWriter for testing."""
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)
        return writer

    @pytest.fixture
    def test_block(self):
        """Create a test memory block."""
        return MemoryBlock(
            id="test-block-123",
            type="task",
            text="Test block content",
            tags=["test"],
            created_by="test-user",
        )

    def test_write_memory_block_blocked_on_main(self, mock_writer, test_block):
        """Test that write_memory_block is blocked on main branch."""
        with pytest.raises(MainBranchProtectionError) as exc_info:
            mock_writer.write_memory_block(test_block, branch="main")

        assert "write_memory_block" in str(exc_info.value)
        assert "main" in str(exc_info.value)

    def test_write_memory_block_allowed_on_feature_branch(self, mock_writer, test_block):
        """Test that write_memory_block is allowed on feature branches."""
        with patch.object(mock_writer, "_get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # Should not raise an exception
            try:
                mock_writer.write_memory_block(test_block, branch="feature-branch")
            except MainBranchProtectionError:
                pytest.fail("write_memory_block should be allowed on feature branches")

    def test_delete_memory_block_blocked_on_main(self, mock_writer):
        """Test that delete_memory_block is blocked on main branch."""
        with pytest.raises(MainBranchProtectionError) as exc_info:
            mock_writer.delete_memory_block("test-block-123", branch="main")

        assert "delete_memory_block" in str(exc_info.value)
        assert "main" in str(exc_info.value)

    def test_commit_changes_blocked_on_main_persistent(self, mock_writer):
        """Test that commit_changes is blocked on main branch with persistent connection."""
        # Mock persistent connection on main branch
        mock_writer._use_persistent = True
        mock_writer._current_branch = "main"
        mock_writer._persistent_connection = MagicMock()

        with pytest.raises(MainBranchProtectionError) as exc_info:
            mock_writer.commit_changes("Test commit")

        assert "commit_changes" in str(exc_info.value)
        assert "main" in str(exc_info.value)

    def test_commit_changes_blocked_on_main_non_persistent(self, mock_writer):
        """Test that commit_changes is blocked on main branch without persistent connection."""
        # Mock non-persistent connection that returns main as active branch
        with patch.object(mock_writer, "_get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"active_branch": "main"}
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # The method should return (False, None) when protection blocks it
            success, commit_hash = mock_writer.commit_changes("Test commit")
            assert success is False
            assert commit_hash is None

    def test_add_to_staging_blocked_on_main(self, mock_writer):
        """Test that add_to_staging is blocked on main branch."""
        # Mock non-persistent connection that returns main as active branch
        with patch.object(mock_writer, "_get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"active_branch": "main"}
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            with pytest.raises(MainBranchProtectionError) as exc_info:
                mock_writer.add_to_staging()

            assert "add_to_staging" in str(exc_info.value)
            assert "main" in str(exc_info.value)

    def test_push_to_remote_blocked_on_main(self, mock_writer):
        """Test that push_to_remote is blocked on main branch."""
        with pytest.raises(MainBranchProtectionError) as exc_info:
            mock_writer.push_to_remote("origin", branch="main")

        assert "push_to_remote" in str(exc_info.value)
        assert "main" in str(exc_info.value)

    def test_write_block_proof_blocked_on_main(self, mock_writer):
        """Test that write_block_proof is blocked on main branch."""
        with pytest.raises(MainBranchProtectionError) as exc_info:
            mock_writer.write_block_proof("test-block", "create", "abc123", branch="main")

        assert "write_block_proof" in str(exc_info.value)
        assert "main" in str(exc_info.value)

    def test_operations_allowed_on_feature_branch(self, mock_writer, test_block):
        """Test that all operations are allowed on feature branches."""
        with patch.object(mock_writer, "_get_connection") as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"active_branch": "feature-branch"}
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # These should not raise MainBranchProtectionError
            try:
                # Test write operations (will fail for other reasons, but not protection)
                mock_writer.write_memory_block(test_block, branch="feature-branch")
            except MainBranchProtectionError:
                pytest.fail("write_memory_block should be allowed on feature branches")
            except Exception:
                pass  # Other exceptions are expected due to mocking

            try:
                mock_writer.delete_memory_block("test-block", branch="feature-branch")
            except MainBranchProtectionError:
                pytest.fail("delete_memory_block should be allowed on feature branches")
            except Exception:
                pass

            try:
                mock_writer.push_to_remote("origin", branch="feature-branch")
            except MainBranchProtectionError:
                pytest.fail("push_to_remote should be allowed on feature branches")
            except Exception:
                pass


class TestSQLLinkManagerBranchProtection:
    """Test branch protection in SQLLinkManager."""

    @pytest.fixture
    def mock_link_manager(self):
        """Create a mocked SQLLinkManager for testing."""
        config = DoltConnectionConfig()
        manager = SQLLinkManager(config)
        return manager

    def test_upsert_link_blocked_on_main(self, mock_link_manager):
        """Test that upsert_link is blocked on main branch."""
        # Mock active_branch to return main
        with patch.object(
            type(mock_link_manager), "active_branch", new_callable=PropertyMock
        ) as mock_branch:
            mock_branch.return_value = "main"

            with pytest.raises(MainBranchProtectionError) as exc_info:
                mock_link_manager.upsert_link(
                    from_id="block-1", to_id="block-2", relation=PMRelationType.DEPENDS_ON
                )

            assert "upsert_link" in str(exc_info.value)
            assert "main" in str(exc_info.value)

    def test_delete_link_blocked_on_main(self, mock_link_manager):
        """Test that delete_link is blocked on main branch."""
        with patch.object(
            type(mock_link_manager), "active_branch", new_callable=PropertyMock
        ) as mock_branch:
            mock_branch.return_value = "main"

            with pytest.raises(MainBranchProtectionError) as exc_info:
                mock_link_manager.delete_link(
                    from_id="block-1", to_id="block-2", relation=PMRelationType.DEPENDS_ON
                )

            assert "delete_link" in str(exc_info.value)
            assert "main" in str(exc_info.value)

    def test_bulk_upsert_blocked_on_main(self, mock_link_manager):
        """Test that bulk_upsert is blocked on main branch."""
        with patch.object(
            type(mock_link_manager), "active_branch", new_callable=PropertyMock
        ) as mock_branch:
            mock_branch.return_value = "main"

            links = [("block-1", "block-2", PMRelationType.DEPENDS_ON, None)]

            with pytest.raises(MainBranchProtectionError) as exc_info:
                mock_link_manager.bulk_upsert(links)

            assert "bulk_upsert" in str(exc_info.value)
            assert "main" in str(exc_info.value)

    def test_delete_links_for_block_blocked_on_main(self, mock_link_manager):
        """Test that delete_links_for_block is blocked on main branch."""
        with patch.object(
            type(mock_link_manager), "active_branch", new_callable=PropertyMock
        ) as mock_branch:
            mock_branch.return_value = "main"

            with pytest.raises(MainBranchProtectionError) as exc_info:
                mock_link_manager.delete_links_for_block("block-1")

            assert "delete_links_for_block" in str(exc_info.value)
            assert "main" in str(exc_info.value)

    def test_operations_allowed_on_feature_branch(self, mock_link_manager):
        """Test that all operations are allowed on feature branches."""
        with patch.object(
            type(mock_link_manager), "active_branch", new_callable=PropertyMock
        ) as mock_branch:
            mock_branch.return_value = "feature-branch"

            # Mock database operations to avoid actual DB calls
            with patch.object(mock_link_manager, "_get_connection") as mock_get_conn:
                mock_conn = MagicMock()
                mock_cursor = MagicMock()
                mock_conn.cursor.return_value = mock_cursor
                mock_get_conn.return_value = mock_conn

                # These should not raise MainBranchProtectionError
                try:
                    mock_link_manager.upsert_link(
                        from_id="block-1", to_id="block-2", relation=PMRelationType.DEPENDS_ON
                    )
                except MainBranchProtectionError:
                    pytest.fail("upsert_link should be allowed on feature branches")
                except Exception:
                    pass  # Other exceptions are expected due to mocking


class TestBranchProtectionErrorMessages:
    """Test that error messages are informative and helpful."""

    def test_error_message_includes_operation_and_branch(self):
        """Test that error messages include operation and branch information."""
        error = MainBranchProtectionError("test_operation", "main")

        assert "test_operation" in str(error)
        assert "main" in str(error)
        assert "protected branch" in str(error)
        assert "read-only" in str(error)
        assert "feature branch" in str(error)

    def test_error_message_includes_multiple_protected_branches(self):
        """Test that error messages show all protected branches."""
        protected_branches = ["main", "production", "staging"]
        error = MainBranchProtectionError("test_operation", "main", protected_branches)

        assert "test_operation" in str(error)
        assert "main" in str(error)
        for branch in protected_branches:
            assert branch in str(error)


class TestBranchProtectionIntegration:
    """Integration tests for branch protection across components."""

    def test_protection_consistent_across_components(self):
        """Test that protection behavior is consistent across DoltWriter and SQLLinkManager."""
        config = DoltConnectionConfig()
        writer = DoltMySQLWriter(config)
        link_manager = SQLLinkManager(config)

        # Both should protect main branch
        assert writer._is_branch_protected("main")
        assert link_manager._is_branch_protected("main")

        # Both should allow feature branches
        assert not writer._is_branch_protected("feature-branch")
        assert not link_manager._is_branch_protected("feature-branch")

    def test_protection_respects_environment_configuration(self):
        """Test that protection respects environment variable configuration."""
        with patch.dict(os.environ, {"DOLT_PROTECTED_BRANCHES": "production,staging"}):
            import importlib
            import infra_core.memory_system.dolt_mysql_base as base_module

            importlib.reload(base_module)

            config = DoltConnectionConfig()
            writer = DoltMySQLWriter(config)

            # Should protect configured branches
            assert writer._is_branch_protected("production")
            assert writer._is_branch_protected("staging")

            # Should not protect main (not in config)
            assert not writer._is_branch_protected("main")

            # Should not protect feature branches
            assert not writer._is_branch_protected("feature-branch")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
