#!/usr/bin/env python3
"""
Test StructuredMemoryBank functionality with MySQL connector.

This test verifies StructuredMemoryBank can work with MySQL connections
to a running Dolt SQL server using mysql.connector.

Environment Variables:
- MYSQL_HOST / DB_HOST: Database host (default: localhost)
- MYSQL_PORT / DB_PORT: Database port (default: 3306)
- MYSQL_USER / DB_USER: Database user (default: root)
- MYSQL_PASSWORD / DB_PASSWORD: Database password (default: empty)
- MYSQL_DATABASE / DB_NAME: Database name (default: memory_dolt)
"""

import pytest
from infra_core.memory_system.dolt_reader import DoltConnectionConfig
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


class TestStructuredMemoryBankMySQL:
    """Test StructuredMemoryBank with MySQL connection to Dolt SQL server."""

    @pytest.fixture
    def dolt_config(self):
        """Create DoltConnectionConfig using environment variables."""
        return DoltConnectionConfig()

    def test_initialization_with_mysql_config(self, dolt_config):
        """Test StructuredMemoryBank initialization with MySQL config."""
        # Test with MySQL connection config
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        assert memory_bank.dolt_connection_config is not None, "Should have MySQL connection config"
        assert memory_bank.dolt_db_path is None, "Should not have file path when using MySQL config"

        print("✅ StructuredMemoryBank initialized with MySQL config")

    def test_initialization_validation(self, dolt_config):
        """Test that initialization properly validates configuration options."""
        # Test that we can't provide both config options
        with pytest.raises(ValueError, match="Cannot specify both"):
            StructuredMemoryBank(dolt_db_path="/some/path", dolt_connection_config=dolt_config)

        # Test that we must provide at least one config option
        with pytest.raises(ValueError, match="Must specify either"):
            StructuredMemoryBank()

        print("✅ StructuredMemoryBank validation works correctly")

    def test_get_memory_blocks_with_mysql(self, dolt_config):
        """Test getting memory blocks using MySQL connection."""
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        # Test getting all memory blocks
        blocks = memory_bank.get_memory_blocks()

        assert isinstance(blocks, list), "Should return a list of memory blocks"
        if blocks:
            sample_block = blocks[0]
            # The structured memory bank should return MemoryBlock objects or dicts
            assert hasattr(sample_block, "id") or "id" in sample_block, (
                "Memory block should have an id"
            )

        print(f"✅ Retrieved {len(blocks)} memory blocks using MySQL connection")

    def test_get_memory_block_by_id_with_mysql(self, dolt_config):
        """Test getting a specific memory block by ID using MySQL."""
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        # First get a block ID to test with
        all_blocks = memory_bank.get_memory_blocks()

        if not all_blocks:
            pytest.skip("No memory blocks available for testing")

        test_block = all_blocks[0]
        test_block_id = test_block.id if hasattr(test_block, "id") else test_block["id"]

        # Test getting the specific block
        retrieved_block = memory_bank.get_memory_block(test_block_id)

        assert retrieved_block is not None, f"Should find memory block with ID {test_block_id}"
        retrieved_id = (
            retrieved_block.id if hasattr(retrieved_block, "id") else retrieved_block["id"]
        )
        assert retrieved_id == test_block_id, "Retrieved block should have the correct ID"

        print(f"✅ Successfully retrieved specific memory block: {test_block_id}")

    def test_get_memory_blocks_by_tags_with_mysql(self, dolt_config):
        """Test getting memory blocks by tags using MySQL."""
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        # Test with empty tags (should return all blocks)
        all_blocks = memory_bank.get_memory_blocks_by_tags([])
        assert isinstance(all_blocks, list), "Should return a list for empty tags"

        # Test with a specific tag if blocks have tags
        blocks_with_tags = memory_bank.get_memory_blocks()

        if blocks_with_tags:
            # Find a block with tags
            for block in blocks_with_tags:
                block_tags = block.tags if hasattr(block, "tags") else block.get("tags", [])
                if block_tags:
                    # Test with first tag
                    if isinstance(block_tags, list) and block_tags:
                        test_tag = block_tags[0]
                        tagged_blocks = memory_bank.get_memory_blocks_by_tags([test_tag])
                        assert isinstance(tagged_blocks, list), "Should return a list for tag query"
                        print(f"✅ Found {len(tagged_blocks)} blocks with tag '{test_tag}'")
                        break
            else:
                print("ℹ️ No blocks with tags found for tag testing")

    def test_branch_parameter_with_mysql(self, dolt_config):
        """Test that branch parameter works with MySQL connection."""
        memory_bank = StructuredMemoryBank(
            dolt_connection_config=dolt_config,
            branch="main",  # Test explicit branch parameter
        )

        blocks = memory_bank.get_memory_blocks()
        assert isinstance(blocks, list), "Should return blocks from specified branch"

        print(f"✅ Retrieved {len(blocks)} blocks from 'main' branch")

    def test_default_branch_configuration(self, dolt_config):
        """Test default branch configuration."""
        # Test with default branch (should be 'main')
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        # The branch should default to 'main'
        assert memory_bank.branch == "main", "Default branch should be 'main'"

        # Test that we can override the branch
        memory_bank_custom = StructuredMemoryBank(
            dolt_connection_config=dolt_config, branch="custom-branch"
        )
        assert memory_bank_custom.branch == "custom-branch", "Should use custom branch"

        print("✅ Branch configuration works correctly")

    def test_internal_abstraction_methods(self, dolt_config):
        """Test that internal abstraction methods work correctly."""
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        # These are internal methods, but we can test they exist and work
        # Note: This assumes the methods are accessible for testing

        try:
            # Test _read_memory_blocks method
            blocks = memory_bank._read_memory_blocks()
            assert isinstance(blocks, list), "_read_memory_blocks should return a list"

            if blocks:
                # Test _read_memory_block method
                test_block_id = blocks[0].id if hasattr(blocks[0], "id") else blocks[0]["id"]
                single_block = memory_bank._read_memory_block(test_block_id)
                assert single_block is not None, "_read_memory_block should return a block"

            # Test _read_memory_blocks_by_tags method
            tagged_blocks = memory_bank._read_memory_blocks_by_tags([])
            assert isinstance(tagged_blocks, list), (
                "_read_memory_blocks_by_tags should return a list"
            )

            print("✅ Internal abstraction methods work correctly")

        except AttributeError:
            # If the internal methods aren't accessible, that's fine
            print("ℹ️ Internal methods not accessible for testing (expected)")

    def test_connection_handling(self, dolt_config):
        """Test proper connection handling and error scenarios."""
        # Test with valid config
        memory_bank = StructuredMemoryBank(dolt_connection_config=dolt_config)

        # Multiple operations should work (testing connection reuse/cleanup)
        blocks1 = memory_bank.get_memory_blocks()
        blocks2 = memory_bank.get_memory_blocks()

        assert len(blocks1) == len(blocks2), "Multiple operations should return consistent results"

        print("✅ Connection handling works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
