import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import datetime

from services.web_api.app import app  # Import your FastAPI app
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.schemas.common import (
    ConfidenceScore,
    BlockLink,
)  # Assuming these are used by MemoryBlock


# Fixture for TestClient
@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# Sample MemoryBlock data for testing
@pytest.fixture
def sample_memory_blocks_data():
    return [
        MemoryBlock(
            id="block-1",
            type="knowledge",
            text="This is the first test block.",
            tags=["test", "api"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={"source": "test_fixture"},
            schema_version=1,
            links=[BlockLink(to_id="block-2", relation="related_to")],
            confidence=ConfidenceScore(ai=0.9),
        ),
        MemoryBlock(
            id="block-2",
            type="knowledge",
            text="This is the second test block, linked from the first.",
            tags=["test", "linked"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata={"source": "test_fixture"},
            schema_version=1,
        ),
    ]


def test_get_all_blocks_success(client: TestClient, sample_memory_blocks_data: list[MemoryBlock]):
    """Test successful retrieval of all memory blocks."""
    # Convert Pydantic models to dicts for JSON comparison, handling datetime
    expected_json_response = [block.model_dump(mode="json") for block in sample_memory_blocks_data]

    # Mock the StructuredMemoryBank instance and its get_all_memory_blocks method
    mock_memory_bank = MagicMock()
    mock_memory_bank.get_all_memory_blocks.return_value = sample_memory_blocks_data

    # Patch app.state.memory_bank to return our mock
    # The path to 'app.state.memory_bank' depends on where 'app' is initialized
    # and how lifespan context manager sets it. Assuming it's accessible via app.state.
    with patch("services.web_api.app.lifespan", MagicMock()):  # Mock lifespan to prevent real setup
        app.state.memory_bank = mock_memory_bank  # Direct assignment for simplicity here

        response = client.get("/api/blocks")

        assert response.status_code == 200
        assert response.json() == expected_json_response
        mock_memory_bank.get_all_memory_blocks.assert_called_once_with()  # Called with default 'main' branch

        # Clean up app.state.memory_bank if necessary, though TestClient should isolate
        if hasattr(app.state, "memory_bank"):
            del app.state.memory_bank


def test_get_all_blocks_memory_bank_unavailable(client: TestClient):
    """Test retrieval when memory bank is not available (e.g., initialization failed)."""
    # Ensure memory_bank is None on app.state
    # This might require careful handling of the app's lifespan context for testing
    with patch("services.web_api.app.lifespan", MagicMock()):  # Mock lifespan
        original_memory_bank = getattr(app.state, "memory_bank", None)
        app.state.memory_bank = None

        response = client.get("/api/blocks")

        assert response.status_code == 500
        # Updated expected error detail to include the 500 from the HTTPException's string representation
        assert response.json() == {
            "detail": "An unexpected error occurred: 500: Memory bank not available"
        }

        # Restore original memory_bank if it existed
        if original_memory_bank is not None:
            app.state.memory_bank = original_memory_bank
        elif hasattr(app.state, "memory_bank"):
            del app.state.memory_bank


def test_get_all_blocks_general_exception(client: TestClient):
    """Test retrieval when get_all_memory_blocks raises an unexpected exception."""
    mock_memory_bank = MagicMock()
    mock_memory_bank.get_all_memory_blocks.side_effect = Exception("Unexpected DB error")

    with patch("services.web_api.app.lifespan", MagicMock()):  # Mock lifespan
        app.state.memory_bank = mock_memory_bank

        response = client.get("/api/blocks")

        assert response.status_code == 500
        assert response.json() == {"detail": "An unexpected error occurred: Unexpected DB error"}
        mock_memory_bank.get_all_memory_blocks.assert_called_once()

        if hasattr(app.state, "memory_bank"):
            del app.state.memory_bank
