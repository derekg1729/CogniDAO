"""
PropertyMapper: Utility for converting between Pydantic metadata and block_properties table.

This module provides the core logic for the Property-Schema Split by handling
bidirectional conversion between metadata dictionaries and property rows.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .schemas.common import BlockProperty

logger = logging.getLogger(__name__)


class PropertyMapper:
    """
    Utility class for converting between Pydantic metadata models and block_properties table rows.

    This is the core logic for the Property-Schema Split, providing:
    - Type detection and variant column mapping (text/number/json)
    - Universal extras support for all metadata types
    - Bidirectional conversion with validation
    - Error handling for unsupported types
    """

    # Type mappings for variant column selection
    TEXT_TYPES = (str, bool, type(None))
    NUMBER_TYPES = (int, float)
    JSON_TYPES = (dict, list, tuple, set)

    @classmethod
    def detect_property_type(cls, value: Any) -> str:
        """
        Detect the appropriate property_type and variant column for a value.

        Args:
            value: The property value to analyze

        Returns:
            Property type string ('text', 'number', 'json', 'bool', 'date', 'select', 'multi_select')
        """
        if value is None:
            return "text"  # Store None as empty text

        # Handle datetime objects
        if isinstance(value, datetime):
            return "date"

        # Handle enum types
        if isinstance(value, Enum):
            return "select"

        # Handle basic Python types
        if isinstance(value, bool):
            return "bool"
        elif isinstance(value, str):
            return "text"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, (list, tuple, set)):
            # Check if it's a list of strings (multi_select case)
            if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
                return "multi_select"
            return "json"
        elif isinstance(value, dict):
            return "json"
        else:
            # Fallback to JSON for complex objects
            return "json"

    @classmethod
    def convert_to_variant_value(cls, value: Any, property_type: str) -> Dict[str, Any]:
        """
        Convert a Python value to the appropriate variant column values.

        Args:
            value: The property value to convert
            property_type: The detected property type

        Returns:
            Dictionary with exactly one of: property_value_text, property_value_number, property_value_json
            and optionally 'fallback_type' if the type was changed during conversion
        """
        # Initialize all variant columns to None
        result = {
            "property_value_text": None,
            "property_value_number": None,
            "property_value_json": None,
        }

        if value is None:
            # This should not happen now with FIX-01, but keeping for safety
            # If somehow a None reaches here, store as empty text
            result["property_value_text"] = ""
        elif property_type == "number":
            result["property_value_number"] = float(value)
        elif property_type in ["json", "multi_select"]:
            # For JSON types, we need to ensure the value is actually serializable
            try:
                # Test JSON serialization first
                import json

                json.dumps(value)  # This will raise an exception if not serializable
                result["property_value_json"] = value  # Dolt will handle JSON serialization
            except (TypeError, ValueError) as e:
                # If JSON serialization fails, fall back to string representation
                logger.warning(f"Value not JSON serializable, converting to string: {e}")
                try:
                    result["property_value_text"] = str(value)
                    result["fallback_type"] = "text"  # Indicate type change
                except Exception:
                    # If even string conversion fails, store error info
                    raise ValueError(f"Cannot serialize value of type {type(value).__name__}")
        elif property_type == "date":
            # Convert datetime to ISO string
            if isinstance(value, datetime):
                result["property_value_text"] = value.isoformat()
            else:
                result["property_value_text"] = str(value)
        elif property_type == "bool":
            # Store booleans as text "true"/"false"
            result["property_value_text"] = "true" if value else "false"
        elif property_type == "select":
            # Store enum values as their string representation
            result["property_value_text"] = (
                str(value.value) if isinstance(value, Enum) else str(value)
            )
        else:  # property_type == "text" or fallback
            result["property_value_text"] = str(value) if value is not None else ""

        return result

    @classmethod
    def convert_from_variant_value(
        cls,
        property_type: str,
        text_value: Optional[str],
        number_value: Optional[float],
        json_value: Optional[Any],
    ) -> Any:
        """
        Convert variant column values back to appropriate Python type.

        Args:
            property_type: The property type stored in the database
            text_value: Value from property_value_text column
            number_value: Value from property_value_number column
            json_value: Value from property_value_json column

        Returns:
            The converted Python value
        """
        if property_type == "number":
            return number_value
        elif property_type in ["json", "multi_select"]:
            return json_value
        elif property_type == "date":
            if text_value:
                try:
                    return datetime.fromisoformat(text_value)
                except ValueError:
                    logger.warning(f"Failed to parse datetime: {text_value}")
                    return text_value
            return None
        elif property_type == "bool":
            if text_value is None:
                return None
            return text_value.lower() == "true"
        elif property_type == "select":
            return text_value
        else:  # property_type == "text" or fallback
            # CR-04 fix: Convert empty string back to None for round-trip compatibility
            if text_value == "":
                return None
            return text_value

    @classmethod
    def decompose_metadata(
        cls, block_id: str, metadata_dict: Dict[str, Any], is_computed: bool = False
    ) -> List[BlockProperty]:
        """
        Convert a metadata dictionary to a list of BlockProperty instances.

        This method handles universal extras support by storing any field as a property.

        FIX-01: Fields with None values are skipped entirely to avoid CHECK constraint
        violations (chk_exactly_one_value_nonnull requires exactly one non-NULL variant column).

        Args:
            block_id: ID of the memory block
            metadata_dict: The metadata dictionary to decompose
            is_computed: Whether these properties are computed/AI-generated

        Returns:
            List of BlockProperty instances ready for database insertion
        """
        properties = []
        now = datetime.now()

        for field_name, value in metadata_dict.items():
            # Store all fields, including None values (as empty strings for CHECK constraint)
            # This ensures round-trip compatibility with the tests
            # FIX-01: Skip None values entirely to avoid CHECK constraint violations
            if value is None:
                logger.debug(f"Skipping field '{field_name}' with None value for block {block_id}")
                continue

            try:
                # Detect appropriate property type
                property_type = cls.detect_property_type(value)

                # Convert to variant column values
                variant_values = cls.convert_to_variant_value(value, property_type)

                # Check if there was a type fallback during conversion
                final_property_type = variant_values.pop("fallback_type", property_type)

                # Create BlockProperty instance
                prop = BlockProperty(
                    block_id=block_id,
                    property_name=field_name,
                    property_type=final_property_type,
                    is_computed=is_computed,
                    created_at=now,
                    updated_at=now,
                    **variant_values,
                )

                properties.append(prop)

            except Exception as e:
                logger.error(f"Failed to decompose property {field_name}: {e}")
                # Store problematic values as JSON for debugging
                try:
                    fallback_prop = BlockProperty(
                        block_id=block_id,
                        property_name=f"_error_{field_name}",
                        property_type="json",
                        property_value_json={"error": str(e), "original_value": str(value)},
                        is_computed=is_computed,
                        created_at=now,
                        updated_at=now,
                    )
                    properties.append(fallback_prop)
                except Exception as fallback_error:
                    logger.error(
                        f"Failed to create fallback property for {field_name}: {fallback_error}"
                    )
                    # If even the fallback fails, skip this property entirely
                    continue

        return properties

    @classmethod
    def compose_metadata(cls, properties: List[BlockProperty]) -> Dict[str, Any]:
        """
        Convert a list of BlockProperty instances back to a metadata dictionary.

        This method reconstructs the original metadata including any extras that were stored.

        Args:
            properties: List of BlockProperty instances from the database

        Returns:
            Reconstructed metadata dictionary
        """
        metadata_dict = {}

        for prop in properties:
            try:
                # Convert variant column values back to Python type
                value = cls.convert_from_variant_value(
                    prop.property_type,
                    prop.property_value_text,
                    prop.property_value_number,
                    prop.property_value_json,
                )

                # Handle error properties (skip them in normal reconstruction)
                if prop.property_name.startswith("_error_"):
                    logger.warning(f"Skipping error property: {prop.property_name}")
                    continue

                metadata_dict[prop.property_name] = value

            except Exception as e:
                logger.error(f"Failed to compose property {prop.property_name}: {e}")
                # Store problematic properties as raw values for debugging
                metadata_dict[f"_raw_{prop.property_name}"] = {
                    "property_type": prop.property_type,
                    "text": prop.property_value_text,
                    "number": prop.property_value_number,
                    "json": prop.property_value_json,
                    "error": str(e),
                }

        return metadata_dict

    @classmethod
    def validate_metadata_schema(
        cls, metadata_dict: Dict[str, Any], metadata_model_class: type
    ) -> Dict[str, Any]:
        """
        Validate a metadata dictionary against a Pydantic model and separate extras.

        Args:
            metadata_dict: The metadata dictionary to validate
            metadata_model_class: The Pydantic model class to validate against

        Returns:
            Dictionary with 'valid_fields', 'extras', and 'validation_errors'
        """
        model_fields = set(metadata_model_class.model_fields.keys())

        # Pre-separate known vs unknown fields
        valid_fields_to_test = {k: v for k, v in metadata_dict.items() if k in model_fields}
        extras = {k: v for k, v in metadata_dict.items() if k not in model_fields}

        try:
            # Test validation only with known fields (no extras)
            instance = metadata_model_class.model_validate(valid_fields_to_test)
            valid_fields = instance.model_dump()

            return {"valid_fields": valid_fields, "extras": extras, "validation_errors": []}

        except ValidationError as e:
            # Extract field errors
            field_errors = {}
            for error in e.errors():
                field_path = ".".join(str(x) for x in error["loc"])
                field_errors[field_path] = error["msg"]

            # Separate valid from invalid fields within the known fields
            truly_valid_fields = {}

            for field_name, value in valid_fields_to_test.items():
                if field_name not in field_errors:
                    truly_valid_fields[field_name] = value
                # Fields with errors are not included in valid_fields

            return {
                "valid_fields": truly_valid_fields,
                "extras": extras,
                "validation_errors": list(field_errors.items()),
            }

    @classmethod
    def merge_extras_into_metadata(
        cls, valid_metadata: Dict[str, Any], extras: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge extras back into a validated metadata dictionary.

        Args:
            valid_metadata: Dictionary of fields that passed validation
            extras: Dictionary of extra fields to merge in

        Returns:
            Combined metadata dictionary
        """
        result = valid_metadata.copy()

        # Add extras with a prefix to avoid conflicts
        for key, value in extras.items():
            # Avoid overwriting valid fields
            if key not in result:
                result[key] = value
            else:
                # If there's a conflict, store with a prefix
                result[f"_extra_{key}"] = value
                logger.warning(
                    f"Extra field {key} conflicts with valid field, stored as _extra_{key}"
                )

        return result
