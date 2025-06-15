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

# Import the tool and its models for testing the get_block endpoint
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    GetMemoryBlockOutput,
)


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
            links=[BlockLink(from_id="block-1", to_id="block-2", relation="related_to")],
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


# Sample single memory block for get_block tests
@pytest.fixture
def sample_memory_block():
    return MemoryBlock(
        id="test-block-123",
        type="knowledge",
        text="This is a test memory block for individual retrieval.",
        tags=["test", "api", "get"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        metadata={"source": "test_fixture", "purpose": "testing get_block endpoint"},
        schema_version=1,
    )


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
        mock_memory_bank.get_all_memory_blocks.assert_called_once_with(
            branch="main"
        )  # Called with default 'main' branch

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

    # Configure dolt_writer mock with active_branch
    mock.dolt_writer = MagicMock()
    mock.dolt_writer.active_branch = "main"

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


# Tests for the new GET /api/blocks/{id} endpoint
@patch("services.web_api.routes.blocks_router.get_memory_block_tool")
def test_get_block_success(mock_get_block_tool, client_with_mock_bank, sample_memory_block):
    """Test successful retrieval of a specific memory block by ID."""
    # Configure mock to return success output with new consistent API
    mock_output = GetMemoryBlockOutput(
        success=True,
        blocks=[sample_memory_block],  # New consistent API - always a list
        error=None,
        timestamp=datetime.datetime.utcnow(),
    )
    mock_get_block_tool.return_value = mock_output

    # Make the request
    response = client_with_mock_bank.get(f"/api/blocks/{sample_memory_block.id}")

    # Verify the response
    assert response.status_code == 200
    assert response.json() == sample_memory_block.model_dump(mode="json")

    # Verify cache headers
    assert "Cache-Control" in response.headers
    assert "max-age=3600" in response.headers["Cache-Control"]
    assert "public" in response.headers["Cache-Control"]

    # Verify the tool was called correctly
    mock_get_block_tool.assert_called_once()
    _, kwargs = mock_get_block_tool.call_args
    assert "memory_bank" in kwargs
    assert "block_id" in kwargs
    assert kwargs["block_id"] == sample_memory_block.id


@patch("services.web_api.routes.blocks_router.get_memory_block_tool")
def test_get_block_not_found(mock_get_block_tool, client_with_mock_bank):
    """Test retrieval of a non-existent memory block by ID."""
    # Configure mock to return not found output with new consistent API
    mock_output = GetMemoryBlockOutput(
        success=False,
        blocks=[],  # Empty list when not found
        error="Memory block with ID 'non-existent-id' not found.",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_get_block_tool.return_value = mock_output

    # Make the request
    response = client_with_mock_bank.get("/api/blocks/non-existent-id")

    # Verify the response
    assert response.status_code == 404
    error_response = response.json()
    assert "detail" in error_response
    assert "not found" in error_response["detail"]

    # Verify the tool was called correctly
    mock_get_block_tool.assert_called_once()


@patch("services.web_api.routes.blocks_router.get_memory_block_tool")
def test_get_block_error(mock_get_block_tool, client_with_mock_bank):
    """Test error handling when retrieving a memory block encounters an error."""
    # Configure mock to return an error output with new consistent API
    mock_output = GetMemoryBlockOutput(
        success=False,
        blocks=[],  # Empty list on error
        error="Database connection error",
        timestamp=datetime.datetime.utcnow(),
    )
    mock_get_block_tool.return_value = mock_output

    # Make the request
    response = client_with_mock_bank.get("/api/blocks/error-block-id")

    # Verify the response
    assert response.status_code == 500
    error_response = response.json()
    assert "detail" in error_response
    assert "Failed to retrieve block" in error_response["detail"]

    # Verify the tool was called correctly
    mock_get_block_tool.assert_called_once()


def test_get_block_memory_bank_unavailable(client_with_mock_bank):
    """Test error handling when memory bank is unavailable for get_block."""
    app.state.memory_bank = None  # Simulate bank not being available
    response = client_with_mock_bank.get("/api/blocks/any-id")
    assert response.status_code == 500
    assert "Memory bank service unavailable" in response.text


@patch("services.web_api.routes.blocks_router.get_memory_block_tool")
def test_get_block_exception(mock_get_block_tool, client_with_mock_bank):
    """Test error handling when get_memory_block_tool raises an exception."""
    # Configure mock to raise an exception
    mock_get_block_tool.side_effect = Exception("Unexpected tool error")

    # Make the request
    response = client_with_mock_bank.get("/api/blocks/exception-block-id")

    # Verify the response
    assert response.status_code == 500
    error_response = response.json()
    assert "detail" in error_response
    assert "An unexpected error occurred during block retrieval" in error_response["detail"]
    assert "Unexpected tool error" in error_response["detail"]

    # Verify the tool was called correctly
    mock_get_block_tool.assert_called_once()


# Helper to create a valid task block payload
def create_valid_task_payload() -> Dict[str, Any]:
    """Create a valid task block creation payload for testing."""
    return {
        "type": "task",
        "text": "Test task block creation",
        "metadata": {
            "x_agent_id": "test-runner",
            "title": "Test Task Title",
            "description": "Valid task metadata for testing",
            "owner": "test_owner_id",
            "status": "backlog",  # Updated from 'todo' to 'backlog' to match new schema
            # Other fields from TaskMetadata are optional or have defaults
            "acceptance_criteria": ["Test passes"],  # Required by ExecutableMetadata
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
        assert block_arg.metadata["title"] == payload["metadata"]["title"]
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
    assert response_data["metadata"]["title"] == payload["metadata"]["title"]


def test_create_block_invalid_metadata(
    client_with_mock_bank, mock_memory_bank, ensure_task_schema_registered
):
    """Test block creation failure due to invalid metadata for the type."""
    payload = create_valid_task_payload()
    del payload["metadata"]["title"]  # Make metadata invalid (title is required for TaskMetadata)

    response = client_with_mock_bank.post("/api/blocks", json=payload)

    assert response.status_code == 422, (
        f"Expected 422, got {response.status_code}. Response: {response.text}"
    )
    # The router prefixes the tool's error message
    assert "Input validation failed: Metadata validation failed for type 'task'" in response.text
    # Ensure the specific field causing issues is mentioned (from Pydantic error details)
    assert (
        "Field required" in response.text or "'title'" in response.text
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


def test_get_blocks_with_type_filter(
    client: TestClient, sample_memory_blocks_data: list[MemoryBlock]
):
    """Test filtering memory blocks by type."""
    # Add a block with a different type to the test data
    project_block = MemoryBlock(
        id="project-block-1",
        type="project",  # Distinct type for testing the filter
        text="This is a project block.",
        tags=["test", "project"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        metadata={"source": "test_fixture", "name": "Test Project"},
        schema_version=1,
    )
    test_blocks = sample_memory_blocks_data + [project_block]

    # Update sample blocks to have explicit types
    for i, block in enumerate(sample_memory_blocks_data):
        block.type = "knowledge"

    # Convert Pydantic models to dicts for JSON comparison
    expected_knowledge_blocks = [
        block.model_dump(mode="json") for block in sample_memory_blocks_data
    ]
    expected_project_blocks = [project_block.model_dump(mode="json")]

    # Mock the memory bank
    mock_memory_bank = MagicMock()
    mock_memory_bank.get_all_memory_blocks.return_value = test_blocks

    with patch("services.web_api.app.lifespan", MagicMock()):
        app.state.memory_bank = mock_memory_bank

        # Test filtering by knowledge type
        response_knowledge = client.get("/api/blocks?type=knowledge")
        assert response_knowledge.status_code == 200
        assert response_knowledge.json() == expected_knowledge_blocks

        # Test filtering by project type
        response_project = client.get("/api/blocks?type=project")
        assert response_project.status_code == 200
        assert response_project.json() == expected_project_blocks

        # Test with a type that doesn't exist
        response_none = client.get("/api/blocks?type=nonexistent")
        assert response_none.status_code == 200
        assert response_none.json() == []

        # Verify the memory bank was called each time
        assert mock_memory_bank.get_all_memory_blocks.call_count == 3

        if hasattr(app.state, "memory_bank"):
            del app.state.memory_bank


def test_get_blocks_with_no_type_filter(
    client: TestClient, sample_memory_blocks_data: list[MemoryBlock]
):
    """Test that all blocks are returned when no type filter is applied."""
    # Add a block with a different type to the test data
    project_block = MemoryBlock(
        id="project-block-1",
        type="project",
        text="This is a project block.",
        tags=["test", "project"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        metadata={"source": "test_fixture", "name": "Test Project"},
        schema_version=1,
    )
    test_blocks = sample_memory_blocks_data + [project_block]

    # Set explicit types on sample blocks
    for block in sample_memory_blocks_data:
        block.type = "knowledge"

    # Convert all blocks to JSON format for comparison
    expected_all_blocks = [block.model_dump(mode="json") for block in test_blocks]

    # Mock the memory bank
    mock_memory_bank = MagicMock()
    mock_memory_bank.get_all_memory_blocks.return_value = test_blocks

    with patch("services.web_api.app.lifespan", MagicMock()):
        app.state.memory_bank = mock_memory_bank

        # Test without any type filter - should return all blocks
        response = client.get("/api/blocks")
        assert response.status_code == 200
        assert response.json() == expected_all_blocks

        # Verify the memory bank was called
        mock_memory_bank.get_all_memory_blocks.assert_called_once()

        if hasattr(app.state, "memory_bank"):
            del app.state.memory_bank


def test_get_blocks_with_empty_type_filter(
    client: TestClient, sample_memory_blocks_data: list[MemoryBlock]
):
    """Test behavior when an empty type filter is provided."""
    # Mock the memory bank with the sample data
    mock_memory_bank = MagicMock()
    mock_memory_bank.get_all_memory_blocks.return_value = sample_memory_blocks_data

    # Convert blocks to JSON format for comparison
    expected_blocks = [block.model_dump(mode="json") for block in sample_memory_blocks_data]

    with patch("services.web_api.app.lifespan", MagicMock()):
        app.state.memory_bank = mock_memory_bank

        # Test with empty type parameter
        response = client.get("/api/blocks?type=")
        assert response.status_code == 200
        # An empty string type won't match any blocks, so we get all blocks back
        # This is because the current implementation only filters if type is truthy
        assert response.json() == expected_blocks

        # Verify the memory bank was called
        mock_memory_bank.get_all_memory_blocks.assert_called_once()

        if hasattr(app.state, "memory_bank"):
            del app.state.memory_bank


def test_get_blocks_with_case_insensitive_filtering(client: TestClient):
    """Test case insensitivity in the type filter with the case_insensitive parameter."""
    # Create test blocks with different valid types
    knowledge_block = MemoryBlock(
        id="knowledge-block",
        type="knowledge",
        text="This is a knowledge block.",
        tags=["test", "case-insensitive"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        metadata={"source": "test_fixture"},
        schema_version=1,
    )

    project_block = MemoryBlock(
        id="project-block",
        type="project",
        text="This is a project block.",
        tags=["test", "case-insensitive"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        metadata={"source": "test_fixture"},
        schema_version=1,
    )

    task_block = MemoryBlock(
        id="task-block",
        type="task",
        text="This is a task block.",
        tags=["test", "case-insensitive"],
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
        metadata={"source": "test_fixture"},
        schema_version=1,
    )

    test_blocks = [knowledge_block, project_block, task_block]

    # Mock the memory bank
    mock_memory_bank = MagicMock()
    mock_memory_bank.get_all_memory_blocks.return_value = test_blocks

    with patch("services.web_api.app.lifespan", MagicMock()):
        app.state.memory_bank = mock_memory_bank

        # Test with case sensitivity (default) - uppercase should not match
        response = client.get("/api/blocks?type=PROJECT")
        assert response.status_code == 200
        assert len(response.json()) == 0  # No matches with case-sensitive search

        # Test with case insensitivity enabled - uppercase should match lowercase 'project'
        response = client.get("/api/blocks?type=PROJECT&case_insensitive=true")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "project-block"

        # Test with mixed case and case insensitivity
        response = client.get("/api/blocks?type=pRoJeCt&case_insensitive=true")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == "project-block"

        # Verify the memory bank was called each time
        assert mock_memory_bank.get_all_memory_blocks.call_count == 3

        if hasattr(app.state, "memory_bank"):
            del app.state.memory_bank
