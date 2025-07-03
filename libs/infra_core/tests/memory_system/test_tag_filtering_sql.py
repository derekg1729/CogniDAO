#!/usr/bin/env python3
"""
Test file to check SQL queries for tag filtering in Dolt.
"""

import logging
import json
from unittest.mock import patch
from infra_core.memory_system.dolt_reader import DoltMySQLReader
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_read_memory_blocks_by_tags_integration():
    """
    Integration test for DoltMySQLReader.read_memory_blocks_by_tags.

    This test calls the actual method to ensure it correctly queries blocks
    with the specified tag. It mocks the underlying database connection to
    control the data and avoid reliance on a live Dolt instance.
    """
    # Mock the config and the connection
    mock_config = DoltConnectionConfig()
    tag_to_find = "core-document"

    # This is the expected data returned from the mocked database query
    mock_sql_return = [
        {
            "id": "test-id-123",
            "namespace_id": "legacy",
            "type": "doc",
            "tags": json.dumps([tag_to_find, "other-tag"]),
            "text": "some text",
            "schema_version": "1",
            "state": "draft",
            "visibility": "internal",
            "block_version": 1,
            "parent_id": None,
            "has_children": False,
            "source_file": None,
            "source_uri": None,
            "confidence": None,
            "created_by": "test",
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
            "embedding": None,
        }
    ]

    # We use patch to intercept the _get_connection method
    with patch.object(DoltMySQLReader, "_get_connection") as mock_get_connection:
        # We also patch read_block_properties to isolate this test
        with patch.object(
            DoltMySQLReader, "read_block_properties", return_value=[]
        ) as _mock_read_properties:
            # Set up the mock connection and cursor
            mock_connection = mock_get_connection.return_value
            mock_cursor = mock_connection.cursor.return_value
            mock_cursor.fetchall.return_value = mock_sql_return

            # Instantiate the reader and call the method under test
            reader = DoltMySQLReader(config=mock_config)
            results = reader.read_memory_blocks_by_tags(tags=[tag_to_find])

            # --- Assertions ---
            # 1. The SQL query should have been executed correctly.
            expected_query = (
                "SELECT id, namespace_id, type, schema_version, text, state, visibility, block_version,"
                " parent_id, has_children, tags, source_file, source_uri, confidence, "
                "created_by, created_at, updated_at, embedding "
                "FROM memory_blocks "
                "WHERE JSON_CONTAINS(tags, %s)"
            )
            # Clean up whitespace for reliable comparison
            normalized_expected_query = " ".join(expected_query.split())

            # Find the actual call from the mock's call list
            actual_call = None
            for call in mock_cursor.execute.call_args_list:
                sql = " ".join(call[0][0].split())
                if "JSON_CONTAINS" in sql:
                    actual_call = call
                    break

            assert actual_call is not None, "The expected SQL query was not executed."

            actual_sql = " ".join(actual_call[0][0].split())
            actual_params = tuple(actual_call[0][1])

            assert normalized_expected_query == actual_sql
            assert (json.dumps(tag_to_find),) == actual_params

            # 2. The method should return the expected results
            assert len(results) == 1, "Should find exactly one matching block"
            block = results[0]
            assert block.id == "test-id-123"
            assert tag_to_find in block.tags, f"Block should have the '{tag_to_find}' tag"

            logger.info("test_read_memory_blocks_by_tags_integration passed successfully.")
