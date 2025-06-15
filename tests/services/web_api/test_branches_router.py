import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import datetime

from services.web_api.app import app
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    DoltListBranchesOutput,
    DoltBranchInfo,
)


# Fixture for TestClient
@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# Sample branch data for testing
@pytest.fixture
def sample_branches_data():
    return [
        DoltBranchInfo(
            name="main",
            hash="abc123def456",
            latest_committer="admin",
            latest_committer_email="admin@example.com",
            latest_commit_date=datetime.datetime.utcnow(),
            latest_commit_message="Initial commit",
            remote="origin",
            branch="main",
            dirty=False,
        ),
        DoltBranchInfo(
            name="feat/test-feature",
            hash="def456ghi789",
            latest_committer="developer",
            latest_committer_email="dev@example.com",
            latest_commit_date=datetime.datetime.utcnow(),
            latest_commit_message="Add test feature",
            remote="",
            branch="",
            dirty=True,
        ),
    ]


@pytest.fixture
def mock_memory_bank():
    """Provides a MagicMock replacement for the StructuredMemoryBank."""
    mock = MagicMock(spec=StructuredMemoryBank)
    return mock


@pytest.fixture
def client_with_mock_bank(mock_memory_bank):
    """Provides a TestClient with the mocked memory bank in app state."""
    original_bank = getattr(app.state, "memory_bank", None)
    app.state.memory_bank = mock_memory_bank
    yield TestClient(app)
    # Restore original bank if it existed, otherwise remove
    if original_bank is not None:
        app.state.memory_bank = original_bank
    elif hasattr(app.state, "memory_bank"):
        del app.state.memory_bank


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_success(mock_dolt_tool, client_with_mock_bank, sample_branches_data):
    """Test successful retrieval of all branches."""
    # Mock the dolt_list_branches_tool return value
    mock_output = DoltListBranchesOutput(
        success=True,
        branches=sample_branches_data,
        active_branch="main",
        message="Found 2 branches. Current branch: main",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_dolt_tool.return_value = mock_output

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 200
    data = response.json()

    # Verify enhanced response structure with branch context
    assert "active_branch" in data
    assert "branches" in data
    assert "total_branches" in data
    assert "timestamp" in data

    # Verify branch context information
    assert data["active_branch"] == "main"
    assert data["total_branches"] == 2

    # Verify branches data
    branches = data["branches"]
    assert len(branches) == 2
    assert branches[0]["name"] == "main"
    assert branches[0]["hash"] == "abc123def456"
    assert branches[1]["name"] == "feat/test-feature"
    assert branches[1]["dirty"] is True


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_memory_bank_unavailable(mock_dolt_tool, client_with_mock_bank):
    """Test retrieval when memory bank is not available."""
    # Set memory bank to None to simulate unavailable state
    original_memory_bank = getattr(app.state, "memory_bank", None)
    app.state.memory_bank = None

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 500
    assert "Memory bank not available" in response.json()["detail"]

    # Restore original memory bank
    if original_memory_bank is not None:
        app.state.memory_bank = original_memory_bank


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_tool_failure(mock_dolt_tool, client_with_mock_bank):
    """Test retrieval when dolt_list_branches_tool reports failure."""
    # Mock tool returning failure
    mock_output = DoltListBranchesOutput(
        success=False,
        branches=[],
        active_branch="unknown",
        message="Failed to list branches",
        error="Database connection failed",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_dolt_tool.return_value = mock_output

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 500
    assert "Failed to retrieve branches" in response.json()["detail"]
    assert "Database connection failed" in response.json()["detail"]


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_tool_exception(mock_dolt_tool, client_with_mock_bank):
    """Test retrieval when dolt_list_branches_tool raises an exception."""
    # Mock tool raising an exception
    mock_dolt_tool.side_effect = Exception("Unexpected database error")

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 500
    assert "An unexpected error occurred" in response.json()["detail"]
    assert "Unexpected database error" in response.json()["detail"]


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_empty_list(mock_dolt_tool, client_with_mock_bank):
    """Test retrieval when no branches are found."""
    # Mock tool returning empty branches list
    mock_output = DoltListBranchesOutput(
        success=True,
        branches=[],
        active_branch="main",
        message="Found 0 branches. Current branch: main",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_dolt_tool.return_value = mock_output

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 200
    data = response.json()
    assert data["total_branches"] == 0
    assert len(data["branches"]) == 0
    assert data["active_branch"] == "main"


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_single_branch(mock_dolt_tool, client_with_mock_bank):
    """Test retrieval with only one branch available."""
    single_branch = [
        DoltBranchInfo(
            name="main",
            hash="abc123def456",
            latest_committer="admin",
            latest_committer_email="admin@example.com",
            latest_commit_date=datetime.datetime.utcnow(),
            latest_commit_message="Initial commit",
            remote="origin",
            branch="main",
            dirty=False,
        )
    ]

    mock_output = DoltListBranchesOutput(
        success=True,
        branches=single_branch,
        active_branch="main",
        message="Found 1 branch. Current branch: main",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_dolt_tool.return_value = mock_output

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 200
    data = response.json()
    assert data["total_branches"] == 1
    branches = data["branches"]
    assert len(branches) == 1
    assert branches[0]["name"] == "main"
    assert branches[0]["dirty"] is False
    assert data["active_branch"] == "main"


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_verify_tool_call(
    mock_dolt_tool, client_with_mock_bank, sample_branches_data
):
    """Test that the dolt_list_branches_tool is called with correct parameters."""
    mock_output = DoltListBranchesOutput(
        success=True,
        branches=sample_branches_data,
        active_branch="main",
        message="Found 2 branches. Current branch: main",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_dolt_tool.return_value = mock_output

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 200

    # Verify the tool was called once with correct parameters
    mock_dolt_tool.assert_called_once()
    args, kwargs = mock_dolt_tool.call_args

    # Verify input_data is DoltListBranchesInput instance
    input_data = args[0]
    assert input_data.__class__.__name__ == "DoltListBranchesInput"

    # Verify memory_bank is passed as second argument
    memory_bank_arg = args[1]
    assert memory_bank_arg is not None


@patch("services.web_api.routes.branches_router.dolt_list_branches_tool")
def test_get_all_branches_json_serialization(mock_dolt_tool, client_with_mock_bank):
    """Test that branch data is properly serialized to JSON."""
    test_branch = DoltBranchInfo(
        name="test-branch",
        hash="test123hash",
        latest_committer="tester",
        latest_committer_email="test@example.com",
        latest_commit_date=datetime.datetime(2025, 6, 15, 12, 0, 0),
        latest_commit_message="Test commit message",
        remote="upstream",
        branch="test-branch",
        dirty=True,
    )

    mock_output = DoltListBranchesOutput(
        success=True,
        branches=[test_branch],
        active_branch="test-branch",
        message="Found 1 branch. Current branch: test-branch",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_dolt_tool.return_value = mock_output

    response = client_with_mock_bank.get("/api/v1/branches")

    assert response.status_code == 200
    data = response.json()
    assert data["total_branches"] == 1
    assert data["active_branch"] == "test-branch"

    branches = data["branches"]
    assert len(branches) == 1

    branch = branches[0]
    assert branch["name"] == "test-branch"
    assert branch["hash"] == "test123hash"
    assert branch["latest_committer"] == "tester"
    assert branch["latest_committer_email"] == "test@example.com"
    assert branch["latest_commit_message"] == "Test commit message"
    assert branch["remote"] == "upstream"
    assert branch["branch"] == "test-branch"
    assert branch["dirty"] is True
