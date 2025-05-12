from fastapi.testclient import TestClient
from services.web_api.app import app

client = TestClient(app)

def test_get_schema_index():
    response = client.get("/schemas/index.json")
    assert response.status_code == 200
    data = response.json()
    assert "schemas" in data
    assert isinstance(data["schemas"], list)
    assert any(s["type"] == "task" for s in data["schemas"])

def test_get_schema_latest():
    response = client.get("/schemas/task/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "TaskMetadata"
    assert data["type"] == "object"
    assert "properties" in data
    assert "project" in data["properties"]

def test_get_schema_invalid_version():
    response = client.get("/schemas/task/999")
    assert response.status_code == 404
    assert "not found" in response.text.lower()

def test_get_schema_unknown_type():
    response = client.get("/schemas/unknown/latest")
    assert response.status_code == 404
    assert "unknown block type" in response.text.lower() 