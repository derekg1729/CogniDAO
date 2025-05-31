"""
Tests for PropertyMapper utility class.
"""

from datetime import datetime
from enum import Enum
from uuid import uuid4
import pytest
from pydantic import ValidationError

from infra_core.memory_system.property_mapper import PropertyMapper
from infra_core.memory_system.schemas.common import BlockProperty
from infra_core.memory_system.schemas.metadata.task import TaskMetadata


class TaskStatus(str, Enum):
    """Test enum for select property type testing."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TestPropertyMapper:
    """Test PropertyMapper functionality."""

    def test_detect_property_type_basic_types(self):
        """Test property type detection for basic Python types."""
        # Text types
        assert PropertyMapper.detect_property_type("hello") == "text"
        assert PropertyMapper.detect_property_type(None) == "text"

        # Number types
        assert PropertyMapper.detect_property_type(42) == "number"
        assert PropertyMapper.detect_property_type(3.14) == "number"

        # Boolean type
        assert PropertyMapper.detect_property_type(True) == "bool"
        assert PropertyMapper.detect_property_type(False) == "bool"

        # Date type
        now = datetime.now()
        assert PropertyMapper.detect_property_type(now) == "date"

        # JSON types
        assert PropertyMapper.detect_property_type({"key": "value"}) == "json"
        assert PropertyMapper.detect_property_type([1, 2, 3]) == "json"

        # Multi-select type (list of strings)
        assert PropertyMapper.detect_property_type(["tag1", "tag2"]) == "multi_select"

        # Enum type
        assert PropertyMapper.detect_property_type(TaskStatus.TODO) == "select"

    def test_convert_to_variant_value_text(self):
        """Test conversion to text variant column."""
        # String value
        result = PropertyMapper.convert_to_variant_value("hello", "text")
        assert result["property_value_text"] == "hello"
        assert result["property_value_number"] is None
        assert result["property_value_json"] is None

        # None value - CR-04 fix: None is stored as empty string to satisfy CHECK constraint
        result = PropertyMapper.convert_to_variant_value(None, "text")
        assert result["property_value_text"] == ""
        assert result["property_value_number"] is None
        assert result["property_value_json"] is None

        # Boolean values
        result = PropertyMapper.convert_to_variant_value(True, "bool")
        assert result["property_value_text"] == "true"

        result = PropertyMapper.convert_to_variant_value(False, "bool")
        assert result["property_value_text"] == "false"

        # Enum value
        result = PropertyMapper.convert_to_variant_value(TaskStatus.IN_PROGRESS, "select")
        assert result["property_value_text"] == "in_progress"

    def test_convert_to_variant_value_number(self):
        """Test conversion to number variant column."""
        # Integer
        result = PropertyMapper.convert_to_variant_value(42, "number")
        assert result["property_value_number"] == 42.0
        assert result["property_value_text"] is None
        assert result["property_value_json"] is None

        # Float
        result = PropertyMapper.convert_to_variant_value(3.14, "number")
        assert result["property_value_number"] == 3.14

    def test_convert_to_variant_value_json(self):
        """Test conversion to JSON variant column."""
        # Dictionary
        data = {"key": "value", "count": 42}
        result = PropertyMapper.convert_to_variant_value(data, "json")
        assert result["property_value_json"] == data
        assert result["property_value_text"] is None
        assert result["property_value_number"] is None

        # List
        data = [1, 2, 3]
        result = PropertyMapper.convert_to_variant_value(data, "json")
        assert result["property_value_json"] == data

        # Multi-select (list of strings)
        data = ["tag1", "tag2", "tag3"]
        result = PropertyMapper.convert_to_variant_value(data, "multi_select")
        assert result["property_value_json"] == data

    def test_convert_to_variant_value_date(self):
        """Test conversion of datetime values."""
        now = datetime(2024, 1, 15, 10, 30, 45)
        result = PropertyMapper.convert_to_variant_value(now, "date")
        assert result["property_value_text"] == "2024-01-15T10:30:45"
        assert result["property_value_number"] is None
        assert result["property_value_json"] is None

    def test_convert_from_variant_value_roundtrip(self):
        """Test round-trip conversion: value -> variant -> value."""
        test_cases = [
            ("hello", "text"),
            (42, "number"),
            (3.14, "number"),
            (True, "bool"),
            (False, "bool"),
            (None, "text"),
            ({"key": "value"}, "json"),
            ([1, 2, 3], "json"),
            (["tag1", "tag2"], "multi_select"),
            (datetime(2024, 1, 15, 10, 30, 45), "date"),
        ]

        for original_value, property_type in test_cases:
            # Convert to variant values
            variant_values = PropertyMapper.convert_to_variant_value(original_value, property_type)

            # Convert back from variant values
            reconstructed_value = PropertyMapper.convert_from_variant_value(
                property_type,
                variant_values["property_value_text"],
                variant_values["property_value_number"],
                variant_values["property_value_json"],
            )

            assert reconstructed_value == original_value, f"Round-trip failed for {original_value}"

    def test_decompose_metadata_basic(self):
        """Test basic metadata decomposition."""
        block_id = str(uuid4())
        metadata = {
            "title": "Test Task",
            "status": "in_progress",
            "priority": "P1",
            "estimate_hours": 5.5,
            "completed": True,
            "tags": ["urgent", "backend"],
            "extra_field": "should work too",
        }

        properties = PropertyMapper.decompose_metadata(block_id, metadata)

        # Should have properties for all fields
        assert len(properties) == 7

        # Check each property was created correctly
        property_names = {prop.property_name for prop in properties}
        expected_names = {
            "title",
            "status",
            "priority",
            "estimate_hours",
            "completed",
            "tags",
            "extra_field",
        }
        assert property_names == expected_names

        # Check specific property types
        prop_by_name = {prop.property_name: prop for prop in properties}

        assert prop_by_name["title"].property_type == "text"
        assert prop_by_name["title"].property_value_text == "Test Task"

        assert prop_by_name["estimate_hours"].property_type == "number"
        assert prop_by_name["estimate_hours"].property_value_number == 5.5

        assert prop_by_name["completed"].property_type == "bool"
        assert prop_by_name["completed"].property_value_text == "true"

        assert prop_by_name["tags"].property_type == "multi_select"
        assert prop_by_name["tags"].property_value_json == ["urgent", "backend"]

    def test_compose_metadata_basic(self):
        """Test basic metadata composition from properties."""
        block_id = str(uuid4())
        now = datetime.now()

        properties = [
            BlockProperty(
                block_id=block_id,
                property_name="title",
                property_type="text",
                property_value_text="Test Task",
                is_computed=False,
                created_at=now,
                updated_at=now,
            ),
            BlockProperty(
                block_id=block_id,
                property_name="estimate_hours",
                property_type="number",
                property_value_number=5.5,
                is_computed=False,
                created_at=now,
                updated_at=now,
            ),
            BlockProperty(
                block_id=block_id,
                property_name="completed",
                property_type="bool",
                property_value_text="true",
                is_computed=False,
                created_at=now,
                updated_at=now,
            ),
            BlockProperty(
                block_id=block_id,
                property_name="tags",
                property_type="multi_select",
                property_value_json=["urgent", "backend"],
                is_computed=False,
                created_at=now,
                updated_at=now,
            ),
        ]

        metadata = PropertyMapper.compose_metadata(properties)

        expected = {
            "title": "Test Task",
            "estimate_hours": 5.5,
            "completed": True,
            "tags": ["urgent", "backend"],
        }

        assert metadata == expected

    def test_roundtrip_metadata_conversion(self):
        """Test full round-trip: metadata -> properties -> metadata."""
        block_id = str(uuid4())
        original_metadata = {
            "title": "Test Task",
            "description": "A test task for validation",
            "status": "in_progress",
            "assignee": "user_123",
            "priority": "P1",
            "estimate_hours": 8.0,
            "start_date": datetime(2024, 1, 15, 9, 0, 0),
            "tags": ["test", "validation"],
            "completed": False,
            "metadata_info": {"complexity": "medium", "risk": "low"},
            "extra_custom_field": "this should be preserved",
        }

        # Convert to properties
        properties = PropertyMapper.decompose_metadata(block_id, original_metadata)

        # Convert back to metadata
        reconstructed_metadata = PropertyMapper.compose_metadata(properties)

        # Should match exactly
        assert reconstructed_metadata == original_metadata

    def test_validate_metadata_schema_valid(self):
        """Test metadata validation with valid TaskMetadata."""
        metadata_dict = {
            "x_agent_id": "test_agent",
            "title": "Test Task",
            "description": "A test task",
            "status": "in_progress",
            "assignee": "user_123",
            "acceptance_criteria": ["Must work", "Must be tested"],
            "priority": "P1",
            "estimate_hours": 5.0,
        }

        result = PropertyMapper.validate_metadata_schema(metadata_dict, TaskMetadata)

        assert result["validation_errors"] == []
        assert result["extras"] == {}
        assert "x_agent_id" in result["valid_fields"]
        assert "title" in result["valid_fields"]

    def test_validate_metadata_schema_with_extras(self):
        """Test metadata validation with extra fields."""
        metadata_dict = {
            "x_agent_id": "test_agent",
            "title": "Test Task",
            "description": "A test task",
            "status": "in_progress",
            "assignee": "user_123",
            "acceptance_criteria": ["Must work"],
            "custom_field": "extra value",
            "another_extra": 42,
        }

        result = PropertyMapper.validate_metadata_schema(metadata_dict, TaskMetadata)

        # Should have no validation errors for known fields
        assert result["validation_errors"] == []
        # Extras should be properly separated
        assert result["extras"] == {"custom_field": "extra value", "another_extra": 42}
        assert "title" in result["valid_fields"]
        assert "custom_field" not in result["valid_fields"]

    def test_validate_metadata_schema_with_validation_errors(self):
        """Test metadata validation with invalid fields."""
        metadata_dict = {
            "x_agent_id": "test_agent",
            "title": "Test Task",
            "description": "A test task",
            "status": "invalid_status",  # Invalid status
            "assignee": "user_123",
            "acceptance_criteria": [],  # Invalid - empty list
            "custom_field": "extra value",
        }

        result = PropertyMapper.validate_metadata_schema(metadata_dict, TaskMetadata)

        # Should have validation errors
        assert len(result["validation_errors"]) > 0

        # Custom field should be in extras
        assert result["extras"]["custom_field"] == "extra value"

        # Valid fields should still be captured
        assert "title" in result["valid_fields"]
        assert "assignee" in result["valid_fields"]

    def test_merge_extras_into_metadata(self):
        """Test merging extras back into validated metadata."""
        valid_metadata = {"title": "Test Task", "status": "in_progress", "assignee": "user_123"}

        extras = {"custom_field": "extra value", "another_field": 42}

        result = PropertyMapper.merge_extras_into_metadata(valid_metadata, extras)

        expected = {
            "title": "Test Task",
            "status": "in_progress",
            "assignee": "user_123",
            "custom_field": "extra value",
            "another_field": 42,
        }

        assert result == expected

    def test_merge_extras_with_conflicts(self):
        """Test merging extras when there are field name conflicts."""
        valid_metadata = {"title": "Test Task", "custom_field": "original value"}

        extras = {
            "custom_field": "conflicting value",  # This conflicts
            "safe_field": "safe value",
        }

        result = PropertyMapper.merge_extras_into_metadata(valid_metadata, extras)

        # Original should be preserved, conflicting one prefixed
        assert result["custom_field"] == "original value"
        assert result["_extra_custom_field"] == "conflicting value"
        assert result["safe_field"] == "safe value"

    def test_error_handling_decompose(self):
        """Test error handling during metadata decomposition."""
        block_id = str(uuid4())

        # Create a problematic value that might cause issues
        class ProblematicObject:
            def __str__(self):
                raise Exception("Cannot convert to string")

            def __repr__(self):
                raise Exception("Cannot convert to string")

        metadata = {"good_field": "works fine", "bad_field": ProblematicObject()}

        properties = PropertyMapper.decompose_metadata(block_id, metadata)

        # Should have only the good field - bad field gets skipped when it can't be serialized at all
        assert len(properties) == 1

        property_names = {prop.property_name for prop in properties}
        assert "good_field" in property_names
        # The bad field should be skipped entirely when it can't be converted to any format
        assert "bad_field" not in property_names
        assert "_error_bad_field" not in property_names

    def test_error_handling_decompose_recoverable(self):
        """Test error handling with a partially recoverable object."""
        block_id = str(uuid4())

        # Create an object that fails JSON serialization but can convert to string
        class JsonFailsButStringWorks:
            def __init__(self, value):
                self.value = value

            def __str__(self):
                return f"JsonFailsButStringWorks({self.value})"

            # This object will fail JSON serialization due to circular reference
            def __getstate__(self):
                raise Exception("Cannot pickle")

        obj = JsonFailsButStringWorks("test")
        obj.circular = obj  # Create circular reference to break JSON

        metadata = {"good_field": "works fine", "recoverable_field": obj}

        properties = PropertyMapper.decompose_metadata(block_id, metadata)

        # Should have properties for both fields
        assert len(properties) == 2

        prop_by_name = {prop.property_name: prop for prop in properties}

        # Good field should work normally
        assert prop_by_name["good_field"].property_type == "text"
        assert prop_by_name["good_field"].property_value_text == "works fine"

        # Recoverable field should fall back to text
        assert prop_by_name["recoverable_field"].property_type == "text"
        assert (
            "JsonFailsButStringWorks(test)" in prop_by_name["recoverable_field"].property_value_text
        )

    def test_error_handling_compose(self):
        """Test error handling during metadata composition."""
        block_id = str(uuid4())
        now = datetime.now()

        # Create a property with invalid data that might cause composition issues
        properties = [
            BlockProperty(
                block_id=block_id,
                property_name="good_field",
                property_type="text",
                property_value_text="works fine",
                is_computed=False,
                created_at=now,
                updated_at=now,
            ),
            BlockProperty(
                block_id=block_id,
                property_name="problem_field",
                property_type="date",
                property_value_text="invalid-date-string",  # Invalid datetime
                is_computed=False,
                created_at=now,
                updated_at=now,
            ),
        ]

        metadata = PropertyMapper.compose_metadata(properties)

        # Good field should work
        assert metadata["good_field"] == "works fine"

        # Problem field should be handled gracefully
        # (In this case, invalid datetime should be returned as string)
        assert metadata["problem_field"] == "invalid-date-string"

    def test_block_property_check_constraint_validator(self):
        """Test the Pydantic validator that enforces the CHECK constraint."""
        block_id = str(uuid4())
        now = datetime.now()

        # Test valid cases - exactly one value column populated

        # Valid: only text value
        prop = BlockProperty(
            block_id=block_id,
            property_name="test_text",
            property_type="text",
            property_value_text="test value",
            is_computed=False,
            created_at=now,
            updated_at=now,
        )
        assert prop.property_value_text == "test value"
        assert prop.property_value_number is None
        assert prop.property_value_json is None

        # Valid: only number value
        prop = BlockProperty(
            block_id=block_id,
            property_name="test_number",
            property_type="number",
            property_value_number=42.5,
            is_computed=False,
            created_at=now,
            updated_at=now,
        )
        assert prop.property_value_number == 42.5
        assert prop.property_value_text is None
        assert prop.property_value_json is None

        # Valid: only json value
        prop = BlockProperty(
            block_id=block_id,
            property_name="test_json",
            property_type="json",
            property_value_json={"key": "value"},
            is_computed=False,
            created_at=now,
            updated_at=now,
        )
        assert prop.property_value_json == {"key": "value"}
        assert prop.property_value_text is None
        assert prop.property_value_number is None

        # Test invalid cases - zero values
        with pytest.raises(ValidationError) as exc_info:
            BlockProperty(
                block_id=block_id,
                property_name="test_empty",
                property_type="text",
                # All value columns are None/missing
                is_computed=False,
                created_at=now,
                updated_at=now,
            )
        assert (
            "Exactly one of property_value_text, property_value_number, or property_value_json must be not-NULL"
            in str(exc_info.value)
        )

        # Test invalid cases - multiple values
        with pytest.raises(ValidationError) as exc_info:
            BlockProperty(
                block_id=block_id,
                property_name="test_multiple",
                property_type="text",
                property_value_text="text value",
                property_value_number=42.0,  # Both text and number populated
                is_computed=False,
                created_at=now,
                updated_at=now,
            )
        assert "Only one property value column can be not-NULL" in str(exc_info.value)

        # Test invalid cases - all three values
        with pytest.raises(ValidationError) as exc_info:
            BlockProperty(
                block_id=block_id,
                property_name="test_all_three",
                property_type="json",
                property_value_text="text value",
                property_value_number=42.0,
                property_value_json={"key": "value"},  # All three populated
                is_computed=False,
                created_at=now,
                updated_at=now,
            )
        assert "Only one property value column can be not-NULL" in str(exc_info.value)
        assert "found 3 non-NULL values" in str(exc_info.value)

    # FIX-01 Tests: None value handling
    def test_fix01_none_field_disappears(self):
        """FIX-01: Test that None fields are skipped entirely during decomposition."""
        block_id = str(uuid4())
        metadata = {"valid_field": "some_value", "none_field": None, "another_valid": 42}

        properties = PropertyMapper.decompose_metadata(block_id, metadata)

        # Should only have 2 properties (None field should be skipped)
        assert len(properties) == 2

        property_names = {prop.property_name for prop in properties}
        assert "valid_field" in property_names
        assert "another_valid" in property_names
        assert "none_field" not in property_names  # None field should disappear

    def test_fix01_field_value_to_none_deletes_row(self):
        """FIX-01: Test that changing a field from value to None removes it from properties."""
        block_id = str(uuid4())

        # Initial metadata with a field
        initial_metadata = {"field1": "value1", "field2": "value2"}
        initial_properties = PropertyMapper.decompose_metadata(block_id, initial_metadata)
        assert len(initial_properties) == 2

        # Updated metadata where field1 becomes None
        updated_metadata = {"field1": None, "field2": "updated_value2"}
        updated_properties = PropertyMapper.decompose_metadata(block_id, updated_metadata)

        # Should only have 1 property now (field1 should be deleted by omission)
        assert len(updated_properties) == 1

        property_names = {prop.property_name for prop in updated_properties}
        assert "field2" in property_names
        assert "field1" not in property_names  # field1 should be gone

        # Verify field2 was updated
        field2_prop = next(prop for prop in updated_properties if prop.property_name == "field2")
        assert field2_prop.property_value_text == "updated_value2"

    def test_fix01_roundtrip_mixed_none_nonnone(self):
        """FIX-01: Test round-trip behavior with mixed None and non-None data."""
        block_id = str(uuid4())

        # Metadata with mixed None and actual values
        original_metadata = {
            "string_field": "hello",
            "none_field": None,
            "number_field": 123,
            "another_none": None,
            "bool_field": True,
        }

        # Decompose -> Properties
        properties = PropertyMapper.decompose_metadata(block_id, original_metadata)

        # Should only have 3 properties (None fields skipped)
        assert len(properties) == 3
        property_names = {prop.property_name for prop in properties}
        assert property_names == {"string_field", "number_field", "bool_field"}

        # Compose back -> Metadata
        recomposed_metadata = PropertyMapper.compose_metadata(properties)

        # Should only contain non-None fields
        expected_metadata = {"string_field": "hello", "number_field": 123, "bool_field": True}
        assert recomposed_metadata == expected_metadata

        # None fields should not appear in recomposed metadata
        assert "none_field" not in recomposed_metadata
        assert "another_none" not in recomposed_metadata
