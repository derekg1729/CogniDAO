from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from services.web_api.app import app

client = TestClient(app)


def test_health_check_success():
    """Test the /healthz endpoint when memory bank and database are working."""
    with patch("services.web_api.routes.health.logger"):
        # Mock the memory bank by setting it directly
        mock_memory_bank = Mock()

        # Mock the dolt_reader and its connection
        mock_dolt_reader = Mock()
        mock_connection = Mock()
        mock_cursor = Mock()

        # Configure the mock chain
        mock_dolt_reader._get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)  # Simple SELECT 1 result

        mock_memory_bank.dolt_reader = mock_dolt_reader
        client.app.state.memory_bank = mock_memory_bank

        try:
            response = client.get("/healthz")
        finally:
            # Clean up
            if hasattr(client.app.state, "memory_bank"):
                delattr(client.app.state, "memory_bank")

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "healthy"
        assert json_response["memory_bank_available"]
        assert json_response["database_connected"]
        assert "connection and query successful" in json_response["details"]["database"]


def test_health_check_no_memory_bank():
    """Test the /healthz endpoint when memory bank is not available."""
    with patch("services.web_api.routes.health.logger"):
        # Ensure memory_bank is not set
        if hasattr(client.app.state, "memory_bank"):
            delattr(client.app.state, "memory_bank")

        response = client.get("/healthz")

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "unhealthy"
        assert not json_response["memory_bank_available"]
        assert not json_response["database_connected"]
        assert "not available in app.state" in json_response["details"]["memory_bank"]


def test_health_check_database_query_failure():
    """Test the /healthz endpoint when database query fails (cursor.execute fails)."""
    with patch("services.web_api.routes.health.logger"):
        # Mock the memory bank by setting it directly
        mock_memory_bank = Mock()

        # Mock the dolt_reader to simulate database query failure
        mock_dolt_reader = Mock()
        mock_connection = Mock()
        mock_cursor = Mock()

        # Configure the mock chain to fail at query execution
        mock_dolt_reader._get_connection.return_value = mock_connection
        mock_connection.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database query failed")

        mock_memory_bank.dolt_reader = mock_dolt_reader
        client.app.state.memory_bank = mock_memory_bank

        try:
            response = client.get("/healthz")
        finally:
            # Clean up
            if hasattr(client.app.state, "memory_bank"):
                delattr(client.app.state, "memory_bank")

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "unhealthy"
        assert json_response["memory_bank_available"]
        assert not json_response["database_connected"]
        assert "connection failed: Database query failed" in json_response["details"]["database"]


def test_health_check_database_error():
    """Test the /healthz endpoint when database connection fails."""
    with patch("services.web_api.routes.health.logger"):
        # Mock the memory bank by setting it directly
        mock_memory_bank = Mock()

        # Mock the dolt_reader to simulate connection failure
        mock_dolt_reader = Mock()
        mock_dolt_reader._get_connection.side_effect = Exception("Database connection error")

        mock_memory_bank.dolt_reader = mock_dolt_reader
        client.app.state.memory_bank = mock_memory_bank

        try:
            response = client.get("/healthz")
        finally:
            # Clean up
            if hasattr(client.app.state, "memory_bank"):
                delattr(client.app.state, "memory_bank")

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["status"] == "unhealthy"
        assert json_response["memory_bank_available"]
        assert not json_response["database_connected"]
        assert (
            "connection failed: Database connection error" in json_response["details"]["database"]
        )
