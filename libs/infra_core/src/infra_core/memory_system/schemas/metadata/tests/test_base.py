"""
Tests for the BaseMetadata schema.
"""

import pytest
from pydantic import ValidationError
from datetime import datetime

from infra_core.memory_system.schemas.metadata.base import BaseMetadata


def test_base_metadata_instantiation():
    """Test successful instantiation with required fields."""
    agent_id = "test_agent_001"
    metadata = BaseMetadata(x_agent_id=agent_id)

    assert metadata.x_agent_id == agent_id
    assert isinstance(metadata.x_timestamp, datetime)
    # Check timestamp is recent (within a reasonable delta, e.g., 5 seconds)
    assert (datetime.now() - metadata.x_timestamp).total_seconds() < 5
    assert metadata.x_tool_id is None
    assert metadata.x_parent_block_id is None
    assert metadata.x_session_id is None


def test_base_metadata_instantiation_with_optionals():
    """Test successful instantiation with optional fields."""
    agent_id = "test_agent_002"
    tool_id = "test_tool_abc"
    parent_block_id = "block_xyz_789"
    session_id = "session_123"

    metadata = BaseMetadata(
        x_agent_id=agent_id,
        x_tool_id=tool_id,
        x_parent_block_id=parent_block_id,
        x_session_id=session_id,
    )

    assert metadata.x_agent_id == agent_id
    assert metadata.x_tool_id == tool_id
    assert metadata.x_parent_block_id == parent_block_id
    assert metadata.x_session_id == session_id
    assert isinstance(metadata.x_timestamp, datetime)


def test_base_metadata_missing_required_field():
    """Test validation error when required field 'x_agent_id' is missing."""
    with pytest.raises(ValidationError) as excinfo:
        BaseMetadata()  # Missing x_agent_id
    # Check that the error message mentions the missing field
    assert "x_agent_id" in str(excinfo.value)
    assert "Field required" in str(excinfo.value)


def test_base_metadata_extra_fields_forbidden():
    """Test validation error when extra fields are provided due to Config.extra = 'forbid'."""
    agent_id = "test_agent_003"
    with pytest.raises(ValidationError) as excinfo:
        BaseMetadata(x_agent_id=agent_id, extra_field="some_value")
    # Check that the error message mentions the extra field
    assert "Extra inputs are not permitted" in str(excinfo.value)
    assert "extra_field" in str(excinfo.value)
