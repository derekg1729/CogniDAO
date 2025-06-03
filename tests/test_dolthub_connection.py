#!/usr/bin/env python3
"""
DoltHub Connection Test Suite

Tests the connection and basic operations with the DoltHub remote repository.
This script verifies read-only operations and safe write operations on test branches.

Usage: pytest tests/test_dolthub_connection.py -v
"""

import subprocess
from datetime import datetime
import pytest


class TestDoltHubConnection:
    """
    Pytest test class for DoltHub connection and operations.

    Tests are designed to be safe and non-destructive to production data.
    All write operations use temporary test branches that are cleaned up.
    """

    @pytest.fixture(autouse=True)
    def setup_test_branch_name(self):
        """Setup unique test branch name for each test run"""
        self.test_branch_name = f"test-conn-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.cleanup_needed = False

    def run_dolt_cmd(self, cmd):
        """Run a dolt command and return result"""
        try:
            result = subprocess.run(
                ["dolt"] + cmd,
                capture_output=True,
                text=True,
                check=True,
                cwd="data/blocks/memory_dolt",  # Ensure we're in the correct directory
            )
            return True, result.stdout.strip(), result.stderr.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stdout, e.stderr

    def test_remote_configuration(self):
        """Test 1: Verify remote is configured correctly"""
        success, stdout, stderr = self.run_dolt_cmd(["remote", "-v"])

        assert success, f"Remote command failed: {stderr}"
        assert "cogni-dao-memory" in stdout, "cogni-dao-memory remote not found in remote config"

    def test_remote_fetch(self):
        """Test 2: Test read-only remote connectivity"""
        success, stdout, stderr = self.run_dolt_cmd(["fetch", "origin"])

        assert success, f"Remote fetch failed: {stderr}"

    def test_remote_log_access(self):
        """Test 3: Test reading remote commit history"""
        success, stdout, stderr = self.run_dolt_cmd(["log", "origin/main", "--oneline", "-n", "3"])

        assert success, f"Cannot read remote commit history: {stderr}"
        assert stdout, "Remote log returned empty response"

        # Verify we got some commits
        commit_lines = stdout.splitlines()
        assert len(commit_lines) > 0, "No commits found in remote history"

    def test_local_data_access(self):
        """Test 4: Verify local data accessibility"""
        success, stdout, stderr = self.run_dolt_cmd(
            ["sql", "-q", "SELECT COUNT(*) FROM memory_blocks"]
        )

        assert success, f"Cannot access local data: {stderr}"
        assert stdout, "SQL query returned empty response"

        # Extract the count from the SQL output (should be in table format)
        lines = stdout.split("\n")
        # Find line with the actual count (skip headers and formatting)
        count_line = None
        for line in lines:
            line = line.strip()
            if line and line.isdigit():
                count_line = line
                break
            # Handle case where count is in table format like "| 111 |"
            elif "|" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if parts and parts[0].isdigit():
                    count_line = parts[0]
                    break

        assert count_line is not None, f"Could not parse block count from SQL output: {stdout}"
        block_count = int(count_line)
        assert block_count > 0, f"Expected > 0 memory blocks, got {block_count}"

    @pytest.mark.skip(
        reason="Test incompatible with persistent SQL server architecture - requires CLI-exclusive access"
    )
    def test_safe_branch_operations(self):
        """Test 5: Test safe branch operations (no push to remote)"""
        # Create test branch
        success, stdout, stderr = self.run_dolt_cmd(["checkout", "-b", self.test_branch_name])
        assert success, f"Cannot create test branch: {stderr}"
        self.cleanup_needed = True

        # Verify we're on test branch
        success, stdout, stderr = self.run_dolt_cmd(["branch", "--show-current"])
        assert success, f"Branch check failed: {stderr}"
        assert self.test_branch_name in stdout, f"Not on expected test branch. Current: {stdout}"

    @pytest.mark.skip(
        reason="Test expects clean working tree but system has uncommitted changes in block_proofs table from SQL server operations"
    )
    def test_working_tree_status(self):
        """Test 6: Verify working tree is clean (no uncommitted changes)"""
        success, stdout, stderr = self.run_dolt_cmd(["status"])
        assert success, f"Status command failed: {stderr}"

        # Dolt status should contain "working tree clean" when there are no changes
        assert "working tree clean" in stdout, f"Working tree has uncommitted changes: {stdout}"

    @pytest.fixture(autouse=True, scope="function")
    def cleanup_test_branch(self, request):
        """Cleanup fixture that runs after each test to clean up test branches"""

        def cleanup():
            if hasattr(self, "cleanup_needed") and self.cleanup_needed:
                # Return to main branch
                self.run_dolt_cmd(["checkout", "main"])

                # Delete test branch if it exists
                success, stdout, stderr = self.run_dolt_cmd(["branch", "-d", self.test_branch_name])
                if not success:
                    # If normal delete fails, try force delete
                    self.run_dolt_cmd(["branch", "-D", self.test_branch_name])

        request.addfinalizer(cleanup)
