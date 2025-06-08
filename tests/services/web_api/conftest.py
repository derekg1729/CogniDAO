import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from services.web_api.app import app
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture
def client():
    """Provides a basic TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_memory_bank():
    """Provides a MagicMock replacement for the StructuredMemoryBank."""
    mock = MagicMock(spec=StructuredMemoryBank)
    mock.get_all_memory_blocks.return_value = []
    mock.create_memory_block.return_value = True  # Default success
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


@pytest.fixture
def client_without_memory_bank():
    """Provides a TestClient with no memory bank to test error conditions."""
    original_bank = getattr(app.state, "memory_bank", None)
    if hasattr(app.state, "memory_bank"):
        del app.state.memory_bank
    yield TestClient(app)
    # Restore original bank if it existed
    if original_bank is not None:
        app.state.memory_bank = original_bank
