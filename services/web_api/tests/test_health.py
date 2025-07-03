from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import DoltPullOutput
from datetime import datetime
from services.web_api.app import app

client = TestClient(app)


def test_health_check_success(client_with_mock_bank, mock_memory_bank):
    """Test that the health endpoint returns a successful response with memory bank available."""
    # Mock the dolt_reader and its connection method
    mock_dolt_reader = MagicMock()
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    mock_dolt_reader._get_connection.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_cursor.execute.return_value = None
    mock_cursor.fetchone.return_value = (1,)

    mock_memory_bank.dolt_reader = mock_dolt_reader

    response = client_with_mock_bank.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["memory_bank_available"] is True
    assert data["database_connected"] is True


def test_health_check_no_memory_bank(client_without_memory_bank):
    """Test health check when memory bank is not available."""
    response = client_without_memory_bank.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["memory_bank_available"] is False
    assert "not available in app.state" in data["details"]["memory_bank"]


def test_health_check_database_error(client_with_mock_bank, mock_memory_bank):
    """Test health check when database connection fails."""
    # Mock the dolt_reader to raise an exception
    mock_dolt_reader = MagicMock()
    mock_dolt_reader._get_connection.side_effect = Exception("Database connection failed")
    mock_memory_bank.dolt_reader = mock_dolt_reader

    response = client_with_mock_bank.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["memory_bank_available"] is True
    assert data["database_connected"] is False
    assert "connection failed" in data["details"]["database"]


def test_refresh_endpoint_success(client_with_mock_bank, mock_memory_bank):
    """Test that the refresh endpoint returns a successful response."""
    # Mock successful dolt_pull_tool result
    with patch(
        "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_pull_tool"
    ) as mock_dolt_pull:
        mock_result = DoltPullOutput(
            success=True,
            message="Successfully pulled from remote 'origin'",
            remote_name="origin",
            branch="main",
            active_branch="main",
            force=False,
            no_ff=False,
            squash=False,
            timestamp=datetime.now(),
        )
        mock_dolt_pull.return_value = mock_result

        response = client_with_mock_bank.post("/api/v1/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Successfully pulled" in data["message"]
        assert "timestamp" in data


def test_refresh_endpoint_handles_up_to_date(client_with_mock_bank, mock_memory_bank):
    """Test that refresh endpoint properly handles 'Everything up-to-date' case."""
    # Mock "Everything up-to-date" result
    with patch(
        "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_pull_tool"
    ) as mock_dolt_pull:
        mock_result = DoltPullOutput(
            success=True,
            message="Everything up-to-date",
            remote_name="origin",
            branch="main",
            active_branch="main",
            force=False,
            no_ff=False,
            squash=False,
            timestamp=datetime.now(),
        )
        mock_dolt_pull.return_value = mock_result

        response = client_with_mock_bank.post("/api/v1/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "up-to-date" in data["message"].lower()


def test_refresh_endpoint_method_validation(client):
    """Test that refresh endpoint only accepts POST requests."""
    # Test GET request should fail
    response = client.get("/api/v1/refresh")
    assert response.status_code == 405  # Method Not Allowed

    # Test PUT request should fail
    response = client.put("/api/v1/refresh")
    assert response.status_code == 405  # Method Not Allowed


def test_refresh_endpoint_no_memory_bank(client_without_memory_bank):
    """Test refresh endpoint when memory bank is not available."""
    response = client_without_memory_bank.post("/api/v1/refresh")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Memory bank not available" in data["message"]
    assert "timestamp" in data


def test_refresh_endpoint_dolt_pull_failure(client_with_mock_bank, mock_memory_bank):
    """Test refresh endpoint when dolt_pull_tool fails."""
    # Mock failed dolt_pull_tool result
    with patch(
        "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_pull_tool"
    ) as mock_dolt_pull:
        mock_result = DoltPullOutput(
            success=False,
            message="Pull operation failed",
            remote_name="origin",
            branch="main",
            active_branch="main",
            force=False,
            no_ff=False,
            squash=False,
            error="Remote repository not accessible",
            timestamp=datetime.now(),
        )
        mock_dolt_pull.return_value = mock_result

        response = client_with_mock_bank.post("/api/v1/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Pull operation failed" in data["message"]
        assert data["error"] == "Remote repository not accessible"
        assert "timestamp" in data


def test_refresh_endpoint_exception_handling(client_with_mock_bank, mock_memory_bank):
    """Test refresh endpoint error handling when an exception occurs."""
    # Mock dolt_pull_tool to raise an exception
    with patch(
        "infra_core.memory_system.tools.agent_facing.dolt_repo_tool.dolt_pull_tool"
    ) as mock_dolt_pull:
        mock_dolt_pull.side_effect = Exception("Unexpected error")

        response = client_with_mock_bank.post("/api/v1/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Refresh operation failed" in data["message"]
        assert "Unexpected error" in data["error"]
        assert "timestamp" in data


def test_health_check_database_query_failure():
    """Test health check when database query fails but connection succeeds."""
    # Mock a memory bank that exists but has a failing database query
    mock_memory_bank = MagicMock()
    mock_dolt_reader = MagicMock()
    mock_connection = MagicMock()
    mock_cursor = MagicMock()

    # Connection succeeds but query fails
    mock_dolt_reader._get_connection.return_value = mock_connection
    mock_connection.cursor.return_value = mock_cursor
    mock_cursor.execute.side_effect = Exception("Query execution failed")

    mock_memory_bank.dolt_reader = mock_dolt_reader

    original_bank = getattr(app.state, "memory_bank", None)
    app.state.memory_bank = mock_memory_bank

    try:
        response = client.get("/healthz")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "unhealthy"
        assert json_response["memory_bank_available"] is True
        assert json_response["database_connected"] is False
        assert "connection failed: Query execution failed" in json_response["details"]["database"]
    finally:
        # Restore original bank if it existed
        if original_bank is not None:
            app.state.memory_bank = original_bank
        elif hasattr(app.state, "memory_bank"):
            del app.state.memory_bank


# These are the old tests from the existing file - keeping for backwards compatibility
def test_health_check_success_old():
    """Test that the health endpoint returns a successful response."""
    # Mock memory bank unavailable for this test
    original_bank = getattr(app.state, "memory_bank", None)
    if hasattr(app.state, "memory_bank"):
        del app.state.memory_bank

    try:
        response = client.get("/healthz")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "unhealthy"
        assert json_response["memory_bank_available"] is False
    finally:
        # Restore original bank if it existed
        if original_bank is not None:
            app.state.memory_bank = original_bank


def test_health_check_no_memory_bank_old():
    """Test health check when memory bank is not available (original test)."""
    # Ensure memory_bank is None
    original_bank = getattr(app.state, "memory_bank", None)
    if hasattr(app.state, "memory_bank"):
        del app.state.memory_bank

    try:
        response = client.get("/healthz")
        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "unhealthy"
        assert json_response["memory_bank_available"] is False
        assert "not available in app.state" in json_response["details"]["memory_bank"]
    finally:
        # Restore original bank if it existed
        if original_bank is not None:
            app.state.memory_bank = original_bank
