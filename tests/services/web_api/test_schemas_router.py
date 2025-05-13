from fastapi.testclient import TestClient
from services.web_api.app import app
from infra_core.memory_system.schemas.registry import SCHEMA_VERSIONS  # Import for version check

client = TestClient(app)


def test_get_schema_index():
    response = client.get("/schemas/index.json")
    assert response.status_code == 200
    assert "Cache-Control" in response.headers
    assert response.headers["Cache-Control"] == "max-age=86400, public"

    data = response.json()
    assert "schemas" in data
    assert isinstance(data["schemas"], list)

    found_task = False
    for s_info in data["schemas"]:
        assert "type" in s_info
        assert "version" in s_info
        assert "latest_version" in s_info
        assert s_info["version"] == s_info["latest_version"]  # Check latest_version logic
        assert "url" in s_info
        assert "latest_url" in s_info
        assert s_info["type"] != "base", "'base' type should be filtered from index"
        if s_info["type"] == "task":
            found_task = True
    assert found_task, "'task' type should be present in index"


def test_get_schema_latest_and_specific_version():
    # Test with 'latest'
    response_latest = client.get("/schemas/task/latest")
    assert response_latest.status_code == 200
    assert "Cache-Control" in response_latest.headers
    assert response_latest.headers["Cache-Control"] == "max-age=86400, public"

    data_latest = response_latest.json()
    assert data_latest["title"] == "TaskMetadata"
    assert data_latest["type"] == "object"
    assert "properties" in data_latest
    assert "project" in data_latest["properties"]

    # Check for required metadata fields
    assert "$id" in data_latest
    assert "x_block_type" in data_latest and data_latest["x_block_type"] == "task"
    assert "x_schema_version" in data_latest

    # Verify inherited BaseMetadata fields are present
    assert "x_agent_id" in data_latest["properties"]
    assert "x_tool_id" in data_latest["properties"]
    assert "x_timestamp" in data_latest["properties"]
    assert "x_parent_block_id" in data_latest["properties"]
    assert "x_session_id" in data_latest["properties"]

    # Check that default values are preserved
    # Example: x_tool_id is Optional with default None
    assert data_latest["properties"]["x_tool_id"].get("default") is None

    # Dynamically get the latest version for task to check $id
    task_latest_version = SCHEMA_VERSIONS["task"]
    assert data_latest["$id"] == f"/schemas/task/{task_latest_version}"
    assert data_latest["x_schema_version"] == task_latest_version

    # Test with specific version (should match latest)
    response_specific = client.get(f"/schemas/task/{task_latest_version}")
    assert response_specific.status_code == 200
    assert "Cache-Control" in response_specific.headers
    assert response_specific.headers["Cache-Control"] == "max-age=86400, public"
    data_specific = response_specific.json()
    assert data_specific == data_latest, (
        "Specific version content should match latest version content"
    )
    assert data_specific["$id"] == f"/schemas/task/{task_latest_version}"


def test_get_schema_invalid_version():
    response = client.get("/schemas/task/999")
    assert response.status_code == 400  # Expect 400 Bad Request for invalid/unsupported version
    assert (
        "not found for type" in response.text.lower() or "invalid version" in response.text.lower()
    )


def test_get_schema_unknown_type():
    response = client.get("/schemas/unknown/latest")
    assert response.status_code == 404
    assert "unknown block type" in response.text.lower()


def test_doc_schema_completeness():
    """Verify schema completeness for the 'doc' type, ensuring all fields, defaults, and enums are included."""
    response = client.get("/schemas/doc/latest")
    assert response.status_code == 200

    schema = response.json()

    # Check basic metadata
    assert schema["$id"].startswith("/schemas/doc/")
    assert schema["x_block_type"] == "doc"
    assert schema["x_schema_version"] == SCHEMA_VERSIONS["doc"]
    assert schema["title"] == "DocMetadata"

    # Check for required and inherited fields
    properties = schema["properties"]
    assert "title" in properties
    assert "format" in properties
    assert "completed" in properties
    assert "x_agent_id" in properties

    # Handle optional enum fields (which use 'anyOf' structure)
    format_property = properties["format"]
    assert "anyOf" in format_property
    # First item in anyOf should be the enum
    enum_option = format_property["anyOf"][0]
    assert "enum" in enum_option
    # Check for expected enum values
    assert set(enum_option["enum"]) == {"markdown", "html", "text", "code"}

    # Check for default values
    assert "default" in format_property
    assert format_property["default"] is None

    # Check for required fields
    assert "title" in schema["required"]

    # Verify default value for 'completed' is preserved
    assert "default" in properties["completed"]
    assert properties["completed"]["default"] is False  # completed defaults to False

    # Check that the schema includes examples from model_config
    assert "examples" in schema
