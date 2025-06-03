from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from services.web_api.app import app

client = TestClient(app)


def test_health_check_success():
    """Test the /healthz endpoint when memory bank and database are working."""
    with patch("services.web_api.routes.health.logger"):
        # Mock the import of get_active_work_items_tool
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_active_work_items_tool"
        ) as mock_tool:
            # Create mock result for successful query
            mock_result = Mock()
            mock_result.success = True
            mock_result.total_count = 2
            mock_tool.return_value = mock_result

            # Mock the memory bank by setting it directly
            mock_memory_bank = Mock()
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
        assert "connected - found 2 active work items" in json_response["details"]["database"]


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
    """Test the /healthz endpoint when database query fails (tool returns success=False)."""
    with patch("services.web_api.routes.health.logger"):
        # Mock the import of get_active_work_items_tool to return failure
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_active_work_items_tool"
        ) as mock_tool:
            mock_result = Mock()
            mock_result.success = False
            mock_result.error = "Database query failed"
            mock_tool.return_value = mock_result

            # Mock the memory bank by setting it directly
            mock_memory_bank = Mock()
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
        assert "query failed: Database query failed" in json_response["details"]["database"]


def test_health_check_database_error():
    """Test the /healthz endpoint when database connection fails."""
    with patch("services.web_api.routes.health.logger"):
        # Mock the import of get_active_work_items_tool to raise an exception
        with patch(
            "infra_core.memory_system.tools.agent_facing.get_active_work_items_tool.get_active_work_items_tool"
        ) as mock_tool:
            mock_tool.side_effect = Exception("Database connection error")

            # Mock the memory bank by setting it directly
            mock_memory_bank = Mock()
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
