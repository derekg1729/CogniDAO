#!/usr/bin/env python3
"""
Test DoltMySQLReader functionality with MySQL connector.

This test verifies the DoltMySQLReader class can properly read memory blocks
from a running Dolt SQL server using mysql.connector.

Environment Variables:
- MYSQL_HOST / DB_HOST: Database host (default: localhost)
- MYSQL_PORT / DB_PORT: Database port (default: 3306)
- MYSQL_USER / DB_USER: Database user (default: root)
- MYSQL_PASSWORD / DB_PASSWORD: Database password (default: empty)
- MYSQL_DATABASE / DB_NAME: Database name (default: memory_dolt)
"""

import pytest
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.dolt_reader import DoltMySQLReader


class TestDoltMySQLReader:
    """Test DoltMySQLReader functionality."""

    @pytest.fixture
    def dolt_config(self):
        """Create DoltConnectionConfig using environment variables."""
        return DoltConnectionConfig()

    @pytest.fixture
    def dolt_reader(self, dolt_config):
        """Create DoltMySQLReader instance."""
        return DoltMySQLReader(dolt_config)

    def test_config_uses_environment_variables(self, dolt_config):
        """Test that DoltConnectionConfig uses environment variables with proper defaults."""
        # These should use defaults if environment variables are not set
        assert dolt_config.host in ["localhost", "127.0.0.1"], (
            f"Unexpected host: {dolt_config.host}"
        )
        assert dolt_config.port == 3306, f"Unexpected port: {dolt_config.port}"
        assert dolt_config.user == "root", f"Unexpected user: {dolt_config.user}"
        assert dolt_config.database == "memory_dolt", f"Unexpected database: {dolt_config.database}"

    def test_read_memory_blocks(self, dolt_reader):
        """Test reading all memory blocks."""
        memory_blocks = dolt_reader.read_memory_blocks(branch="main")

        assert isinstance(memory_blocks, list), "Should return a list of memory blocks"
        if memory_blocks:
            sample_block = memory_blocks[0]
            assert isinstance(sample_block, dict), "Each memory block should be a dictionary"
            assert "id" in sample_block, "Memory block should have an id field"
            assert "text" in sample_block, "Memory block should have a text field"
            assert "type" in sample_block, "Memory block should have a type field"

        print(f"Successfully read {len(memory_blocks)} memory blocks")

    def test_read_specific_memory_block(self, dolt_reader):
        """Test reading a specific memory block by ID."""
        # First get a block ID to test with
        all_blocks = dolt_reader.read_memory_blocks(branch="main")

        if not all_blocks:
            pytest.skip("No memory blocks available for testing")

        test_block_id = all_blocks[0]["id"]

        # Test reading the specific block
        memory_block = dolt_reader.read_memory_block(test_block_id, branch="main")

        assert memory_block is not None, f"Should find memory block with ID {test_block_id}"
        assert memory_block["id"] == test_block_id, "Retrieved block should have the correct ID"

        print(f"Successfully read specific memory block: {test_block_id}")

    def test_read_nonexistent_memory_block(self, dolt_reader):
        """Test reading a memory block that doesn't exist."""
        memory_block = dolt_reader.read_memory_block("nonexistent-id", branch="main")

        assert memory_block is None, "Should return None for nonexistent block"

    def test_read_block_properties(self, dolt_reader):
        """Test reading block properties."""
        # Get a block ID to test with
        all_blocks = dolt_reader.read_memory_blocks(branch="main")

        if not all_blocks:
            pytest.skip("No memory blocks available for testing")

        test_block_id = all_blocks[0]["id"]

        # Test reading block properties
        properties = dolt_reader.read_block_properties(test_block_id, branch="main")

        assert properties is not None, f"Should find properties for block {test_block_id}"
        assert "id" in properties, "Properties should include id field"
        assert "type" in properties, "Properties should include type field"

        print(f"Successfully read properties for block: {test_block_id}")

    def test_batch_read_block_properties(self, dolt_reader):
        """Test batch reading block properties."""
        # Get some block IDs to test with
        all_blocks = dolt_reader.read_memory_blocks(branch="main")

        if not all_blocks:
            pytest.skip("No memory blocks available for testing")

        # Test with first 3 blocks (or fewer if not available)
        test_block_ids = [block["id"] for block in all_blocks[:3]]

        # Test batch reading
        properties_list = dolt_reader.batch_read_block_properties(test_block_ids, branch="main")

        assert isinstance(properties_list, list), "Should return a list of properties"
        assert len(properties_list) <= len(test_block_ids), (
            "Should not return more properties than requested"
        )

        for props in properties_list:
            assert "id" in props, "Each property result should include id field"
            assert "type" in props, "Each property result should include type field"

        print(f"Successfully batch read properties for {len(properties_list)} blocks")

    def test_read_memory_blocks_by_tags(self, dolt_reader):
        """Test reading memory blocks by tags."""
        # First, let's see what blocks exist and what tags they have
        all_blocks = dolt_reader.read_memory_blocks(branch="main")

        if not all_blocks:
            pytest.skip("No memory blocks available for testing")

        # Find a block with tags to test with
        block_with_tags = None
        for block in all_blocks:
            if block.get("tags") and isinstance(block["tags"], (list, str)):
                block_with_tags = block
                break

        if not block_with_tags:
            print("No blocks with tags found, testing with empty tag list")
            # Test with empty tags (should return all blocks)
            tagged_blocks = dolt_reader.read_memory_blocks_by_tags([], branch="main")
            assert len(tagged_blocks) == len(all_blocks), "Empty tag list should return all blocks"
        else:
            # Test with actual tags
            tags = block_with_tags["tags"]
            if isinstance(tags, str):
                import json

                try:
                    tags = json.loads(tags)
                except (json.JSONDecodeError, ValueError):
                    tags = [tags]

            if tags and isinstance(tags, list):
                # Test with first tag
                test_tag = tags[0]
                tagged_blocks = dolt_reader.read_memory_blocks_by_tags([test_tag], branch="main")

                assert isinstance(tagged_blocks, list), "Should return a list of memory blocks"
                print(f"Found {len(tagged_blocks)} blocks with tag '{test_tag}'")

    def test_branch_parameter(self, dolt_reader):
        """Test that branch parameter works correctly."""
        # Test reading from main branch
        main_blocks = dolt_reader.read_memory_blocks(branch="main")

        assert isinstance(main_blocks, list), "Should return a list from main branch"
        print(f"Found {len(main_blocks)} blocks on main branch")

        # Note: We don't test other branches as they may not exist,
        # but the branch switching functionality is tested in the integration test


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
