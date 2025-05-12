from fastapi.testclient import TestClient
from services.web_api.app import app  # Assuming your FastAPI app instance is named 'app'

client = TestClient(app)


def test_health_check():
    """Test the /healthz endpoint."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
