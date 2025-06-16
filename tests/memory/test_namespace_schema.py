"""
Tests for namespace schema implementation.

This module tests that:
1. Namespace Pydantic model works correctly
2. MemoryBlock includes namespace_id field with proper defaults
3. Schema generation includes namespaces table with constraints
4. FK constraint and indexes are properly generated
5. Backwards compatibility is maintained
"""

import pytest
import uuid
from datetime import datetime

from infra_core.memory_system.schemas.namespace import Namespace
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.scripts.generate_dolt_schema import (
    generate_table_schema,
    generate_schema_file,
    FIELD_TYPE_OVERRIDES,
)
from pathlib import Path
import tempfile


class TestNamespaceModel:
    """Test the Namespace Pydantic model."""

    def test_namespace_creation_with_defaults(self):
        """Test creating a namespace with automatic UUID generation."""
        namespace = Namespace(name="Test Namespace", slug="test-namespace", owner_id="user-123")

        # Verify required fields
        assert namespace.name == "Test Namespace"
        assert namespace.slug == "test-namespace"
        assert namespace.owner_id == "user-123"

        # Verify auto-generated fields
        assert namespace.id is not None
        assert len(namespace.id) == 36  # UUID length
        assert isinstance(namespace.created_at, datetime)
        assert namespace.description is None

    def test_namespace_creation_with_all_fields(self):
        """Test creating a namespace with all fields specified."""
        test_id = str(uuid.uuid4())
        test_time = datetime.now()

        namespace = Namespace(
            id=test_id,
            name="Full Namespace",
            slug="full-namespace",
            owner_id="user-456",
            created_at=test_time,
            description="A test namespace with all fields",
        )

        assert namespace.id == test_id
        assert namespace.name == "Full Namespace"
        assert namespace.slug == "full-namespace"
        assert namespace.owner_id == "user-456"
        assert namespace.created_at == test_time
        assert namespace.description == "A test namespace with all fields"

    def test_namespace_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValueError):
            Namespace()  # Missing required fields

        with pytest.raises(ValueError):
            Namespace(name="Test")  # Missing slug and owner_id


class TestMemoryBlockWithNamespace:
    """Test MemoryBlock with namespace_id field."""

    def test_memory_block_default_namespace(self):
        """Test that MemoryBlock defaults to 'legacy' namespace."""
        block = MemoryBlock(type="knowledge", text="Test block content")

        assert block.namespace_id == "legacy"
        assert block.type == "knowledge"
        assert block.text == "Test block content"

    def test_memory_block_custom_namespace(self):
        """Test creating MemoryBlock with custom namespace."""
        block = MemoryBlock(
            namespace_id="custom-namespace-123", type="task", text="Task in custom namespace"
        )

        assert block.namespace_id == "custom-namespace-123"
        assert block.type == "task"
        assert block.text == "Task in custom namespace"

    def test_memory_block_backwards_compatibility(self):
        """Test that existing MemoryBlock creation still works."""
        # This simulates existing code that doesn't specify namespace_id
        block = MemoryBlock(
            id="test-block-123",
            type="doc",
            text="Legacy block creation",
            tags=["legacy", "test"],
            metadata={"source": "migration"},
        )

        # Should default to legacy namespace
        assert block.namespace_id == "legacy"
        assert block.id == "test-block-123"
        assert block.type == "doc"
        assert block.tags == ["legacy", "test"]


class TestSchemaGeneration:
    """Test schema generation with namespace support."""

    def test_namespace_table_generation(self):
        """Test that namespace table is generated correctly."""
        schema_sql = generate_table_schema(Namespace, "namespaces")

        # Verify table structure
        assert "CREATE TABLE IF NOT EXISTS namespaces" in schema_sql
        assert "id VARCHAR(255) PRIMARY KEY" in schema_sql
        assert "name VARCHAR(255) NOT NULL" in schema_sql
        assert "slug VARCHAR(255) NOT NULL" in schema_sql
        assert "owner_id VARCHAR(255) NOT NULL" in schema_sql
        assert "created_at DATETIME NOT NULL" in schema_sql
        assert "description VARCHAR(255) NULL" in schema_sql

    def test_memory_blocks_table_with_namespace_fk(self):
        """Test that memory_blocks table includes namespace FK."""
        schema_sql = generate_table_schema(MemoryBlock, "memory_blocks")

        # Verify namespace_id field
        assert "namespace_id VARCHAR(255) NOT NULL DEFAULT 'legacy'" in schema_sql

        # Verify FK constraint
        assert (
            "CONSTRAINT fk_namespace FOREIGN KEY (namespace_id) REFERENCES namespaces(id)"
            in schema_sql
        )

    def test_field_type_overrides_includes_namespace_id(self):
        """Test that namespace_id has proper type override."""
        assert "namespace_id" in FIELD_TYPE_OVERRIDES
        assert FIELD_TYPE_OVERRIDES["namespace_id"] == "VARCHAR(255)"

    def test_full_schema_generation(self):
        """Test complete schema generation with namespaces."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_schema.sql"

            # Generate schema
            generate_schema_file(output_path)

            # Read generated schema
            with open(output_path, "r") as f:
                schema_content = f.read()

            # Verify namespace table comes first
            namespace_pos = schema_content.find("CREATE TABLE IF NOT EXISTS namespaces")
            memory_blocks_pos = schema_content.find("CREATE TABLE IF NOT EXISTS memory_blocks")
            assert namespace_pos < memory_blocks_pos, (
                "Namespaces table should come before memory_blocks"
            )

            # Verify UNIQUE indexes on namespaces
            assert "CREATE UNIQUE INDEX idx_namespaces_name ON namespaces (name)" in schema_content
            assert "CREATE UNIQUE INDEX idx_namespaces_slug ON namespaces (slug)" in schema_content

            # Verify namespace index on memory_blocks
            assert (
                "CREATE INDEX idx_memory_blocks_namespace ON memory_blocks (namespace_id)"
                in schema_content
            )

            # Verify FK constraint
            assert (
                "CONSTRAINT fk_namespace FOREIGN KEY (namespace_id) REFERENCES namespaces(id)"
                in schema_content
            )


class TestNamespaceIntegration:
    """Integration tests for namespace functionality."""

    def test_namespace_and_memory_block_integration(self):
        """Test that namespace and memory block work together."""
        # Create a namespace
        namespace = Namespace(
            name="Integration Test", slug="integration-test", owner_id="test-user"
        )

        # Create a memory block in that namespace
        block = MemoryBlock(
            namespace_id=namespace.id, type="knowledge", text="Block in integration test namespace"
        )

        # Verify they're linked
        assert block.namespace_id == namespace.id
        assert namespace.name == "Integration Test"

    def test_multiple_blocks_same_namespace(self):
        """Test multiple blocks can share the same namespace."""
        namespace_id = str(uuid.uuid4())

        block1 = MemoryBlock(namespace_id=namespace_id, type="task", text="First block")

        block2 = MemoryBlock(namespace_id=namespace_id, type="doc", text="Second block")

        assert block1.namespace_id == namespace_id
        assert block2.namespace_id == namespace_id
        assert block1.namespace_id == block2.namespace_id

    def test_legacy_namespace_default_behavior(self):
        """Test that legacy namespace is the default for all blocks."""
        blocks = [
            MemoryBlock(type="knowledge", text="Knowledge block"),
            MemoryBlock(type="task", text="Task block"),
            MemoryBlock(type="doc", text="Doc block"),
        ]

        for block in blocks:
            assert block.namespace_id == "legacy"
