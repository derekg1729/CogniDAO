"""
Tests for Epic and Bug metadata models.
"""

import pytest
from datetime import datetime
from infra_core.memory_system.schemas.metadata.epic import EpicMetadata
from infra_core.memory_system.schemas.metadata.bug import BugMetadata


def test_epic_metadata_instantiation():
    """Test that EpicMetadata can be instantiated with required fields."""
    epic = EpicMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        name="Test Epic",
        description="A test epic for unit tests",
    )
    assert epic.owner == "user_456"
    assert epic.name == "Test Epic"
    assert epic.description == "A test epic for unit tests"
    assert epic.status == "planning"  # Default value
    assert epic.completed is False  # Default value


def test_epic_metadata_full():
    """Test that EpicMetadata can be instantiated with all fields."""
    now = datetime.now()
    epic = EpicMetadata(
        x_agent_id="agent_123",
        x_timestamp=now,
        status="in_progress",
        owner="user_456",
        name="Test Epic",
        description="A test epic for unit tests",
        start_date=now,
        target_date=now,
        priority="P1",
        progress_percent=50.0,
        tags=["test", "unit-test"],
        completed=True,
    )
    # Status should be 'completed' when completed=True, regardless of provided status
    assert epic.status == "completed"
    assert epic.owner == "user_456"
    assert epic.priority == "P1"
    assert epic.progress_percent == 50.0
    assert epic.tags == ["test", "unit-test"]
    assert epic.completed is True


def test_epic_metadata_status_completion_sync():
    """Test that status and completion are properly synchronized."""
    # Test that setting completed=True changes status to 'completed'
    epic = EpicMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        name="Test Epic",
        description="A test epic for unit tests",
        status="in_progress",
        completed=True,
    )
    assert epic.status == "completed"
    assert epic.completed is True

    # Test that setting status='completed' changes completed to True
    epic2 = EpicMetadata(
        x_agent_id="agent_123",
        owner="user_456",
        name="Test Epic",
        description="A test epic for unit tests",
        status="completed",
        completed=False,
    )
    assert epic2.status == "completed"
    assert epic2.completed is True


def test_epic_metadata_validation():
    """Test that EpicMetadata validates field values."""
    # Invalid status
    with pytest.raises(ValueError):
        EpicMetadata(
            x_agent_id="agent_123",
            status="invalid_status",
            owner="user_456",
            name="Test Epic",
            description="A test epic for unit tests",
        )

    # Invalid priority
    with pytest.raises(ValueError):
        EpicMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            name="Test Epic",
            description="A test epic for unit tests",
            priority="P6",  # Invalid priority
        )

    # Invalid progress_percent (greater than 100)
    with pytest.raises(ValueError):
        EpicMetadata(
            x_agent_id="agent_123",
            owner="user_456",
            name="Test Epic",
            description="A test epic for unit tests",
            progress_percent=110.0,  # Invalid progress percentage
        )


def test_bug_metadata_instantiation():
    """Test that BugMetadata can be instantiated with required fields."""
    bug = BugMetadata(
        x_agent_id="agent_123",
        reporter="user_456",
        title="Test Bug",
        description="A test bug for unit tests",
    )
    assert bug.reporter == "user_456"
    assert bug.title == "Test Bug"
    assert bug.description == "A test bug for unit tests"
    assert bug.status == "open"  # Default value


def test_bug_metadata_full():
    """Test that BugMetadata can be instantiated with all fields."""
    now = datetime.now()
    bug = BugMetadata(
        x_agent_id="agent_123",
        x_timestamp=now,
        status="in_progress",
        reporter="user_456",
        assignee="user_789",
        title="Test Bug",
        description="A test bug for unit tests",
        priority="P0",
        severity="critical",
        version_found="1.0.0",
        version_fixed="1.0.1",
        steps_to_reproduce="1. Do this\n2. Do that",
        due_date=now,
        labels=["bug", "critical"],
        confidence_score={"human": 0.9, "ai": 0.8},
    )
    assert bug.status == "in_progress"
    assert bug.reporter == "user_456"
    assert bug.assignee == "user_789"
    assert bug.priority == "P0"
    assert bug.severity == "critical"
    assert bug.version_found == "1.0.0"
    assert bug.labels == ["bug", "critical"]


def test_bug_metadata_validation():
    """Test that BugMetadata validates field values."""
    # Invalid status
    with pytest.raises(ValueError):
        BugMetadata(
            x_agent_id="agent_123",
            status="invalid_status",
            reporter="user_456",
            title="Test Bug",
            description="A test bug for unit tests",
        )

    # Invalid priority
    with pytest.raises(ValueError):
        BugMetadata(
            x_agent_id="agent_123",
            reporter="user_456",
            title="Test Bug",
            description="A test bug for unit tests",
            priority="P6",  # Invalid priority
        )

    # Invalid severity
    with pytest.raises(ValueError):
        BugMetadata(
            x_agent_id="agent_123",
            reporter="user_456",
            title="Test Bug",
            description="A test bug for unit tests",
            severity="super-critical",  # Invalid severity
        )
