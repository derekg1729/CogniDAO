import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from typing import Dict, Any
import datetime

from services.web_api.app import app  # Import your FastAPI app
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.schemas.common import (
    ConfidenceScore,
    BlockLink,
)  # Assuming these are used by MemoryBlock
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.registry import (
    SCHEMA_VERSIONS,
    register_metadata,
    _metadata_registry,
)  # Import for tests
from infra_core.memory_system.schemas.metadata.task import (
    TaskMetadata,
)  # Import a concrete metadata type


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
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
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
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
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


@pytest.fixture(autouse=True)
def ensure_task_schema_registered():
    """Ensures TaskMetadata is registered for tests and cleans up."""
    original_registry_state = _metadata_registry.copy()
    original_versions_state = SCHEMA_VERSIONS.copy()

    is_task_registered = (
        "task" in SCHEMA_VERSIONS and _metadata_registry.get("task") is TaskMetadata
    )

    if not is_task_registered:
        SCHEMA_VERSIONS["task"] = (
            2  # Consistent with TaskMetadata actual version if defined, or for test
        )
        register_metadata("task", TaskMetadata)

    yield

    # Clean up: Restore original registry and versions state
    _metadata_registry.clear()
    _metadata_registry.update(original_registry_state)
    SCHEMA_VERSIONS.clear()
    SCHEMA_VERSIONS.update(original_versions_state)


def test_get_all_blocks_bank_unavailable(client_with_mock_bank):
    """Test error handling when memory bank is unavailable."""
    app.state.memory_bank = None  # Simulate bank not being available
    response = client_with_mock_bank.get("/api/blocks")
    assert response.status_code == 500
    assert "Memory bank not available" in response.text


def test_get_all_blocks_bank_exception(client_with_mock_bank, mock_memory_bank):
    """Test error handling when memory bank raises an exception."""
    mock_memory_bank.get_all_memory_blocks.side_effect = Exception("Dolt connection error")
    response = client_with_mock_bank.get("/api/blocks")
    assert response.status_code == 500
    assert "An unexpected error occurred" in response.text
    assert "Dolt connection error" in response.text


# Helper to create a valid task block payload
def create_valid_task_payload() -> Dict[str, Any]:
    return {
        "type": "task",
        "text": "Test task block creation",
        "metadata": {
            "x_agent_id": "test-runner",
            "project": "TestProject",
            "name": "Test Task Name",
            "description": "Valid task metadata for testing",
            "status": "todo",
            # Other fields from TaskMetadata are optional or have defaults
        },
        "tags": ["test", "post"],
    }


def test_create_block_success(
    client_with_mock_bank, mock_memory_bank, ensure_task_schema_registered
):
    """Test successful creation of a block with valid metadata."""
    payload = create_valid_task_payload()

    # The create_memory_block tool will generate an ID. Let's define what we expect.
    # expected_new_block_id = str(uuid.uuid4()) # Removed unused variable

    # Mock the output of the (tool's internal) call to memory_bank.create_memory_block
    # The tool itself constructs the MemoryBlock, so the mock_memory_bank.create_memory_block
    # will be called with a MemoryBlock instance. We'll simulate it returns True.
    mock_memory_bank.create_memory_block.return_value = True

    # When the tool is successful, the endpoint will try to fetch the created block
    # by its ID. We need to mock this call.
    # The tool function `create_memory_block` internally creates the full MemoryBlock
    # and passes it to `memory_bank.create_memory_block`. For the purpose of
    # `get_memory_block` mock, we'll construct a MemoryBlock that would be returned.
    # The ID for this fetched block should match what the tool would determine.
    # Since the tool assigns an ID, and we don't know it beforehand without deeper mocking of the tool,
    # we will mock `get_memory_block` to return a block with *any* ID that the tool might have generated.
    # However, the tool's `output.id` will be used by the router.
    # For simplicity, let's assume the `create_memory_block` tool (if we were to mock it)
    # would return an `output.id`. The router then calls `memory_bank.get_memory_block(output.id)`.

    # Let's adjust how we verify the call to memory_bank.create_memory_block.
    # The tool `create_memory_block` will prepare a MemoryBlock and call it.
    # Then, if successful, the router calls `memory_bank.get_memory_block(id_from_tool_output)`.

    # We need to know the ID the tool would generate to mock get_memory_block effectively.
    # The tool creates a MemoryBlock instance, which auto-generates an ID if not provided.
    # Let's refine the mock:
    # 1. The tool `create_memory_block` is called. It internally:
    #    a. Creates a `MemoryBlock` instance (which gets an ID).
    #    b. Calls `memory_bank.create_memory_block(the_memory_block_instance)`.
    #    c. Returns `CreateMemoryBlockOutput(success=True, id=the_memory_block_instance.id, ...)`
    # 2. The router then calls `memory_bank.get_memory_block(id_from_tool_output)`.

    # We can capture the MemoryBlock passed to the mocked `create_memory_block`
    # and use its ID to mock `get_memory_block`.

    created_block_instance_capture = None

    def capture_block_and_succeed(block_arg: MemoryBlock):
        nonlocal created_block_instance_capture
        created_block_instance_capture = block_arg
        # Ensure the captured block has the input data
        assert block_arg.type == payload["type"]
        assert block_arg.text == payload["text"]
        assert block_arg.metadata["name"] == payload["metadata"]["name"]
        return True  # Simulate success

    mock_memory_bank.create_memory_block.side_effect = capture_block_and_succeed

    def mock_get_block(block_id_arg: str):
        if created_block_instance_capture and block_id_arg == created_block_instance_capture.id:
            return created_block_instance_capture
        return None

    mock_memory_bank.get_memory_block.side_effect = mock_get_block

    response = client_with_mock_bank.post("/api/blocks", json=payload)

    assert response.status_code == 201, (
        f"Expected 201, got {response.status_code}. Response: {response.text}"
    )
    response_data = response.json()

    mock_memory_bank.create_memory_block.assert_called_once()  # Called by the tool
    assert created_block_instance_capture is not None
    mock_memory_bank.get_memory_block.assert_called_once_with(
        created_block_instance_capture.id
    )  # Called by the router

    assert response_data["id"] == created_block_instance_capture.id
    assert response_data["type"] == payload["type"]
    assert response_data["text"] == payload["text"]
    assert response_data["metadata"]["name"] == payload["metadata"]["name"]


def test_create_block_invalid_metadata(
    client_with_mock_bank, mock_memory_bank, ensure_task_schema_registered
):
    """Test block creation failure due to invalid metadata for the type."""
    payload = create_valid_task_payload()
    del payload["metadata"][
        "project"
    ]  # Make metadata invalid (project is required for TaskMetadata)

    response = client_with_mock_bank.post("/api/blocks", json=payload)

    assert response.status_code == 422, (
        f"Expected 422, got {response.status_code}. Response: {response.text}"
    )
    # The router prefixes the tool's error message
    assert "Input validation failed: Metadata validation failed for type 'task'" in response.text
    # Ensure the specific field causing issues is mentioned (from Pydantic error details)
    assert (
        "Field required" in response.text or "'project'" in response.text
    )  # Pydantic's error for missing field
    mock_memory_bank.create_memory_block.assert_not_called()


def test_create_block_invalid_base_model(client_with_mock_bank, mock_memory_bank):
    """Test block creation failure due to invalid base MemoryBlock structure (e.g., missing type)."""
    payload = create_valid_task_payload()
    del payload["type"]  # Make base model invalid
    response = client_with_mock_bank.post("/api/blocks", json=payload)
    assert response.status_code == 422
    # Check for common FastAPI validation error structure for missing fields
    assert "field required" in response.text.lower()
    # FastAPI's error for a missing field 'type' in the JSON body typically includes '"type"' in the 'loc' array.
    assert '"type"' in response.text  # Check if the missing field 'type' (with quotes) is mentioned
    mock_memory_bank.create_memory_block.assert_not_called()


def test_create_block_memory_bank_failure(
    client_with_mock_bank, mock_memory_bank, ensure_task_schema_registered
):
    """Test block creation failure when the memory bank returns False from its create method."""
    payload = create_valid_task_payload()
    mock_memory_bank.create_memory_block.return_value = False  # Underlying bank save fails

    response = client_with_mock_bank.post("/api/blocks", json=payload)

    assert response.status_code == 500
    # The router prefixes the tool's error message "Failed to persist memory block"
    assert "Failed to create block: Failed to persist memory block" in response.text
    mock_memory_bank.create_memory_block.assert_called_once()


def test_create_block_memory_bank_exception(
    client_with_mock_bank, mock_memory_bank, ensure_task_schema_registered
):
    """Test block creation failure when the memory bank's create method raises an exception."""
    payload = create_valid_task_payload()
    mock_memory_bank.create_memory_block.side_effect = Exception(
        "Dolt Write Error"
    )  # Underlying bank save raises

    response = client_with_mock_bank.post("/api/blocks", json=payload)

    assert response.status_code == 500
    # The router prefixes the tool's error message "Unexpected creation failed: Dolt Write Error"
    assert "Failed to create block: Unexpected creation failed: Dolt Write Error" in response.text
    mock_memory_bank.create_memory_block.assert_called_once()
