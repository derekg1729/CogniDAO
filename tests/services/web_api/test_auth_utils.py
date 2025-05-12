import pytest
from fastapi import HTTPException
from unittest.mock import patch
import os  # Required for patch.dict

# Assuming auth_utils.py is in services.web_api
from services.web_api import auth_utils


def test_verify_auth_server_key_not_configured():
    """Test verify_auth when COGNI_API_KEY is not set on the server."""
    with patch.dict(os.environ, {}, clear=True):  # Ensure COGNI_API_KEY is not set
        with pytest.raises(HTTPException) as excinfo:
            auth_utils.verify_auth(authorization="Bearer clientkey")
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "API authentication not configured"


def test_verify_auth_no_client_key_provided():
    """Test verify_auth when the client does not provide an API key (though Header(...) makes it required)."""
    # This case is tricky to test directly as Header(...) makes it a required field by FastAPI.
    # We are testing the logic *within* verify_auth assuming FastAPI provided the header.
    # If FastAPI itself can't find the header, it would raise a 422 before our function is called.
    # For a direct unit test, we simulate an empty/invalid token scenario if it were to pass FastAPI's checks.
    with patch.dict(os.environ, {"COGNI_API_KEY": "testserverkey"}):
        with pytest.raises(HTTPException) as excinfo:
            # The function expects 'authorization' due to `Header(...)`
            # If we call it with None, it would be a TypeError before our logic.
            # Instead, we test the logic for an invalid token format if Header was somehow bypassed or empty.
            # The actual `auth_utils.py` directly compares `authorization != f"Bearer {api_key}"`
            # So, a None or malformed (non-Bearer) would fail that check.
            auth_utils.verify_auth(authorization="invalidtoken")  # Simulating a non-bearer token
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Unauthorized"


def test_verify_auth_malformed_client_key_no_bearer():
    """Test verify_auth when the client key is malformed (missing 'Bearer ')."""
    with patch.dict(os.environ, {"COGNI_API_KEY": "testserverkey"}):
        with pytest.raises(HTTPException) as excinfo:
            auth_utils.verify_auth(authorization="testclientkey")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Unauthorized"


def test_verify_auth_incorrect_client_key():
    """Test verify_auth when the client provides an incorrect API key."""
    with patch.dict(os.environ, {"COGNI_API_KEY": "testserverkey"}):
        with pytest.raises(HTTPException) as excinfo:
            auth_utils.verify_auth(authorization="Bearer wrongclientkey")
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Unauthorized"


def test_verify_auth_correct_key():
    """Test verify_auth when the client provides the correct API key."""
    with patch.dict(os.environ, {"COGNI_API_KEY": "testserverkey"}):
        result = auth_utils.verify_auth(authorization="Bearer testserverkey")
    assert result is True
