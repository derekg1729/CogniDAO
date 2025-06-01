"""
Test for metadata persistence bug in Property-Schema Split approach.

This test verifies that boolean metadata fields are preserved during
update operations and properly committed to the database.
"""

import datetime
import uuid
from infra_core.memory_system.schemas.memory_block import MemoryBlock


def test_boolean_metadata_persistence_bug(temp_memory_bank):
    """
    Test that demonstrates the metadata persistence bug where boolean
    fields get lost during updates due to block_properties table not
    being included in the commit tables list.
    """
    # Use unique ID to avoid conflicts
    unique_id = f"metadata-bug-test-{uuid.uuid4().hex[:8]}"

    # Create test block with boolean metadata
    test_block = MemoryBlock(
        id=unique_id,
        type="knowledge",
        text="Test block for metadata persistence",
        metadata={
            "source": "test_suite",
            "update_run": True,  # Boolean that gets lost
            "flag": False,  # Boolean that gets lost
            "number": 42,  # Should persist
            "text": "value",  # Should persist
        },
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    # Attempt update (this should fail before fix)
    success = temp_memory_bank.update_memory_block(test_block)
    assert success, "Update should succeed"

    # Read back and verify ALL metadata is preserved
    read_back = temp_memory_bank.get_memory_block(unique_id)
    assert read_back is not None, "Block should be found after update"

    # The bug: these boolean fields are lost
    assert read_back.metadata.get("update_run") is True, "Boolean True should be preserved"
    assert read_back.metadata.get("flag") is False, "Boolean False should be preserved"

    # These should work (non-boolean fields)
    assert read_back.metadata.get("source") == "test_suite", "Text field should be preserved"
    assert read_back.metadata.get("number") == 42, "Number field should be preserved"
    assert read_back.metadata.get("text") == "value", "Text value should be preserved"


if __name__ == "__main__":
    # For standalone execution, create temporary memory bank
    import tempfile
    from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
    from infra_core.memory_system.initialize_dolt import initialize_dolt_db

    # Create temporary directories
    temp_dolt = tempfile.mkdtemp(prefix="test_metadata_dolt_")
    temp_chroma = tempfile.mkdtemp(prefix="test_metadata_chroma_")

    try:
        # Initialize test database
        assert initialize_dolt_db(temp_dolt), "Failed to initialize test database"

        # Create memory bank with temp paths
        memory_bank = StructuredMemoryBank(temp_dolt, temp_chroma, "test_collection")

        # Run the test
        test_boolean_metadata_persistence_bug(memory_bank)
        print("✅ Metadata persistence test passed!")

    finally:
        # Cleanup
        import shutil

        shutil.rmtree(temp_dolt, ignore_errors=True)
        shutil.rmtree(temp_chroma, ignore_errors=True)
