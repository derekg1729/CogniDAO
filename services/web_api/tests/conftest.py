import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from services.web_api.app import app
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
import respx
import httpx


@pytest.fixture
def client():
    """Provides a basic TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_memory_bank():
    """Provides a MagicMock replacement for the StructuredMemoryBank."""
    mock = MagicMock(spec=StructuredMemoryBank)
    mock.get_all_memory_blocks.return_value = []
    mock.create_memory_block.return_value = (
        True,
        None,
    )  # Updated to return tuple (success, error_message)
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


@pytest.fixture
def mock_auth():
    """Mock auth dependency that always succeeds."""

    async def mock_verify_auth():
        return True

    return mock_verify_auth


@pytest.fixture
def client_with_mock_auth(mock_auth):
    """Provides a TestClient with mocked auth dependency."""
    from services.web_api.auth_utils import verify_auth

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_auth] = mock_auth
    yield TestClient(app)
    app.dependency_overrides = original_overrides


@pytest.fixture
async def async_client():
    """Shared async test client using new HTTPX API."""
    from services.web_api.auth_utils import verify_auth

    # Mock auth for async tests
    async def mock_verify_auth():
        return True

    # Set up auth override
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[verify_auth] = mock_verify_auth

    # Create client with new API
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # Clean up auth override
    app.dependency_overrides = original_overrides


@pytest.fixture
def mock_langgraph_success():
    """Mock successful LangGraph responses."""
    with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
        # Mock successful thread creation
        respx_mock.post("/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread"})
        )

        # Mock successful run creation
        respx_mock.post("/threads/test_thread/runs").mock(
            return_value=httpx.Response(200, json={"run_id": "test_run"})
        )

        # Mock successful streaming
        respx_mock.get("/threads/test_thread/runs/test_run/stream").mock(
            return_value=httpx.Response(200, text='data: {"type": "complete"}\n\n')
        )

        yield respx_mock


@pytest.fixture
def mock_langgraph_failure():
    """Mock LangGraph failure responses."""
    with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
        # Mock thread creation failure
        respx_mock.post("/threads").mock(
            return_value=httpx.Response(500, json={"detail": "Server error"})
        )

        yield respx_mock
