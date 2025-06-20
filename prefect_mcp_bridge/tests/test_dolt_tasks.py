"""
Tests for Dolt Prefect tasks
"""

import pytest
from unittest.mock import Mock, patch
from prefect_mcp_bridge.dolt import (
    dolt_add_task,
    dolt_commit_task,
    dolt_push_task,
    dolt_add_commit_push_task,
)
from prefect_mcp_bridge.client import MCPClient


class TestDoltTasks:
    """Test suite for Dolt Prefect tasks"""

    def test_dolt_add_task_success(self, mock_mcp_server, test_env_vars, sample_mcp_responses):
        """Test successful dolt_add_task execution"""
        result = dolt_add_task(tables=["test_table"])

        assert result["success"] is True
        assert result["message"] == "Successfully added changes"
        assert "tables_added" in result

    def test_dolt_add_task_no_tables(self, mock_mcp_server, test_env_vars):
        """Test dolt_add_task without specifying tables"""
        result = dolt_add_task()

        assert result["success"] is True
        # Should work with empty payload (add all changes)

    def test_dolt_add_task_with_custom_client(self, mock_mcp_server, test_env_vars):
        """Test dolt_add_task with custom MCP client"""
        custom_client = MCPClient(base_url="http://cogni-mcp:8080")

        result = dolt_add_task(tables=["custom_table"], mcp_client=custom_client)

        assert result["success"] is True

    def test_dolt_add_task_error_handling(self, test_env_vars):
        """Test dolt_add_task error handling"""
        # Use non-existent server to trigger error
        with pytest.raises(Exception) as exc_info:
            dolt_add_task(mcp_client=MCPClient(base_url="http://nonexistent:8080"))

        assert "Dolt add operation failed" in str(exc_info.value)

    def test_dolt_commit_task_success(self, mock_mcp_server, test_env_vars):
        """Test successful dolt_commit_task execution"""
        result = dolt_commit_task(message="Test commit", branch="main", author="test-user")

        assert result["success"] is True
        assert result["commit_hash"] == "abc123def456"
        assert result["message"] == "Test commit by Prefect"

    def test_dolt_commit_task_minimal_args(self, mock_mcp_server, test_env_vars):
        """Test dolt_commit_task with only required arguments"""
        result = dolt_commit_task(message="Minimal commit")

        assert result["success"] is True
        assert "commit_hash" in result

    def test_dolt_commit_task_all_args(self, mock_mcp_server, test_env_vars):
        """Test dolt_commit_task with all optional arguments"""
        result = dolt_commit_task(
            message="Full commit",
            branch="feature-branch",
            author="test-author",
            tables=["table1", "table2"],
        )

        assert result["success"] is True

    def test_dolt_commit_task_error_handling(self, test_env_vars):
        """Test dolt_commit_task error handling"""
        with pytest.raises(Exception) as exc_info:
            dolt_commit_task(
                message="Error test", mcp_client=MCPClient(base_url="http://nonexistent:8080")
            )

        assert "Dolt commit operation failed" in str(exc_info.value)

    def test_dolt_push_task_success(self, mock_mcp_server, test_env_vars):
        """Test successful dolt_push_task execution"""
        result = dolt_push_task(branch="main", remote_name="origin", force=False)

        assert result["success"] is True
        assert result["message"] == "Successfully pushed to origin"
        assert result["branch"] == "main"

    def test_dolt_push_task_defaults(self, mock_mcp_server, test_env_vars):
        """Test dolt_push_task with default arguments"""
        result = dolt_push_task()

        assert result["success"] is True
        # Should use default remote_name="origin" and force=False

    def test_dolt_push_task_force_push(self, mock_mcp_server, test_env_vars):
        """Test dolt_push_task with force push"""
        result = dolt_push_task(force=True)

        assert result["success"] is True

    def test_dolt_push_task_error_handling(self, test_env_vars):
        """Test dolt_push_task error handling"""
        with pytest.raises(Exception) as exc_info:
            dolt_push_task(mcp_client=MCPClient(base_url="http://nonexistent:8080"))

        assert "Dolt push operation failed" in str(exc_info.value)

    def test_dolt_add_commit_push_task_success(self, mock_mcp_server, test_env_vars):
        """Test successful dolt_add_commit_push_task execution"""
        result = dolt_add_commit_push_task(
            message="Full workflow test", branch="main", author="test-user"
        )

        assert result["success"] is True
        assert "add" in result
        assert "commit" in result
        assert "push" in result

        # Verify all sub-operations succeeded
        assert result["add"]["success"] is True
        assert result["commit"]["success"] is True
        assert result["push"]["success"] is True

    def test_dolt_add_commit_push_task_minimal(self, mock_mcp_server, test_env_vars):
        """Test dolt_add_commit_push_task with minimal arguments"""
        result = dolt_add_commit_push_task(message="Minimal workflow")

        assert result["success"] is True
        assert all(key in result for key in ["add", "commit", "push"])

    def test_dolt_add_commit_push_task_with_tables(self, mock_mcp_server, test_env_vars):
        """Test dolt_add_commit_push_task with specific tables"""
        result = dolt_add_commit_push_task(
            message="Table-specific workflow", tables=["table1", "table2"]
        )

        assert result["success"] is True

    def test_dolt_add_commit_push_task_error_handling(self, test_env_vars):
        """Test dolt_add_commit_push_task error handling"""
        result = dolt_add_commit_push_task(
            message="Error test", mcp_client=MCPClient(base_url="http://nonexistent:8080")
        )

        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], str)

    def test_task_names_are_set(self):
        """Test that Prefect task names are properly set"""
        assert dolt_add_task.name == "dolt_add"
        assert dolt_commit_task.name == "dolt_commit"
        assert dolt_push_task.name == "dolt_push"
        assert dolt_add_commit_push_task.name == "dolt_add_commit_push"

    @patch("prefect_mcp_bridge.dolt.MCPClient")
    def test_client_context_management(self, mock_client_class, test_env_vars):
        """Test that MCPClient is used as context manager"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.__enter__.return_value = mock_client
        mock_client.call.return_value = {"success": True}

        dolt_add_task()

        # Verify context manager methods were called
        mock_client.__enter__.assert_called_once()
        mock_client.__exit__.assert_called_once()

    def test_payload_construction(self, mock_mcp_server, test_env_vars):
        """Test that task payloads are constructed correctly"""
        # Test commit task payload with all parameters
        dolt_commit_task(
            message="Test message", branch="test-branch", author="test-author", tables=["table1"]
        )

        # Verify the call was made (exact payload verification would require
        # more detailed mocking of the requests)
        assert len(mock_mcp_server.calls) == 1
        assert mock_mcp_server.calls[0].request.url.endswith("dolt.commit")
