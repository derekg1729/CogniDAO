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


# === LangGraph Chat Test Fixtures ===


@pytest.fixture
def mock_auth():
    """Mock auth dependency for chat tests."""

    def mock_verify_auth():
        return {"user_id": "test_user"}

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
def mock_langgraph_success():
    """Mock successful LangGraph responses with correct URL patterns."""
    with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
        # Mock successful thread creation
        respx_mock.post("/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread_123"})
        )

        # Mock successful streaming (the actual endpoint used by the new implementation)
        respx_mock.post("/threads/test_thread_123/runs/stream").mock(
            return_value=httpx.Response(200, text='data: {"type": "complete"}\n\n')
        )

        yield respx_mock


@pytest.fixture
def mock_langgraph_streaming():
    """Mock LangGraph streaming responses with multiple chunks."""
    with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
        # Mock thread creation
        respx_mock.post("/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread_123"})
        )

        # Mock streaming response with multiple chunks
        stream_content = (
            'data: {"type": "message", "content": "Hello"}\n\n'
            'data: {"type": "message", "content": " world"}\n\n'
            'data: {"type": "message", "content": "!"}\n\n'
            'data: {"type": "done"}\n\n'
        )

        respx_mock.post("/threads/test_thread_123/runs/stream").mock(
            return_value=httpx.Response(200, text=stream_content)
        )

        yield respx_mock


@pytest.fixture
def mock_langgraph_error():
    """Mock LangGraph error responses."""
    with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
        # Mock thread creation failure
        respx_mock.post("/threads").mock(
            return_value=httpx.Response(500, json={"detail": "Internal server error"})
        )

        yield respx_mock
