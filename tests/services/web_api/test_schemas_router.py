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
    assert "$id" in data_latest
    # Dynamically get the latest version for task to check $id
    task_latest_version = SCHEMA_VERSIONS["task"]
    assert data_latest["$id"] == f"/schemas/task/{task_latest_version}"

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
