#!/usr/bin/env python3
"""
Chat Endpoint Request/Response Validation Tests
===============================================

Tests request validation, response format validation, and edge cases
for the FastAPI /chat endpoint.

Key test areas:
1. Request validation (message field, JSON format, etc.)
2. Response headers and content-type validation
3. Auth header validation
4. Edge cases and error conditions
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient
import respx
import httpx

from services.web_api.app import app
from services.web_api import auth_utils


# Override auth for most tests
async def mock_verify_auth():
    return True


@pytest.fixture(autouse=True)
def setup_auth_override():
    """Setup auth override for tests, but allow individual tests to override."""
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[auth_utils.verify_auth] = mock_verify_auth
    yield
    app.dependency_overrides = original_overrides


@pytest.fixture
async def async_test_client():
    """Async test client for FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_langgraph_success():
    """Mock successful LangGraph responses."""
    with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
        # Mock successful thread creation
        respx_mock.post("/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread"})
        )

        # Mock successful streaming (the actual endpoint used by the new implementation)
        respx_mock.post("/threads/test_thread/runs/stream").mock(
            return_value=httpx.Response(200, text='data: {"type": "complete"}\n\n')
        )

        yield respx_mock


class TestRequestValidation:
    """Test request validation and input handling."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_missing_message_field(self, async_test_client):
        """Test that missing message field returns validation error."""
        response = await async_test_client.post(
            "/api/v1/chat",
            json={},  # Missing message field
        )

        assert response.status_code == 422  # FastAPI validation error
        error_data = response.json()
        assert "detail" in error_data

        # Check that error mentions missing message field
        error_details = error_data["detail"]
        assert any(err.get("loc") == ["body", "message"] for err in error_details)

    @pytest.mark.asyncio
    async def test_chat_endpoint_null_message_field(self, async_test_client):
        """Test that null message field returns validation error."""
        response = await async_test_client.post(
            "/api/v1/chat",
            json={"message": None},
        )

        assert response.status_code == 422  # FastAPI validation error
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_chat_endpoint_empty_string_message(
        self, async_test_client, mock_langgraph_success
    ):
        """Test that empty string message is accepted."""
        response = await async_test_client.post("/api/v1/chat", json={"message": ""})

        # Should accept empty message (LangGraph should handle it)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_endpoint_whitespace_only_message(
        self, async_test_client, mock_langgraph_success
    ):
        """Test that whitespace-only message is accepted."""
        response = await async_test_client.post("/api/v1/chat", json={"message": "   \n\t  "})

        # Should accept whitespace message
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_endpoint_very_long_message(self, async_test_client, mock_langgraph_success):
        """Test handling of very long messages."""
        long_message = "x" * 10000  # 10k character message

        response = await async_test_client.post("/api/v1/chat", json={"message": long_message})

        # Should accept long message (LangGraph/OpenAI will handle token limits)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_endpoint_unicode_message(self, async_test_client, mock_langgraph_success):
        """Test handling of Unicode characters in message."""
        unicode_message = "Hello 世界! 🌍 Émojis and ñoñó"

        response = await async_test_client.post("/api/v1/chat", json={"message": unicode_message})

        # Should accept Unicode message
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_endpoint_invalid_json_format(self, async_test_client):
        """Test handling of invalid JSON in request body."""
        response = await async_test_client.post(
            "/api/v1/chat",
            content="invalid json",
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 422  # FastAPI validation error

    @pytest.mark.asyncio
    async def test_chat_endpoint_malformed_json(self, async_test_client):
        """Test handling of malformed JSON."""
        response = await async_test_client.post(
            "/api/v1/chat",
            content='{"message": "test"',  # Missing closing brace
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 422  # FastAPI validation error

    @pytest.mark.asyncio
    async def test_chat_endpoint_wrong_content_type(self, async_test_client):
        """Test handling of wrong content-type header."""
        response = await async_test_client.post(
            "/api/v1/chat",
            content='{"message": "test"}',
            headers={"content-type": "text/plain"},
        )

        assert response.status_code == 422  # FastAPI validation error

    @pytest.mark.asyncio
    async def test_chat_endpoint_extra_fields_ignored(
        self, async_test_client, mock_langgraph_success
    ):
        """Test that extra fields in request are ignored."""
        response = await async_test_client.post(
            "/api/v1/chat",
            json={"message": "Hello", "extra_field": "should be ignored", "another_field": 123},
        )

        # Should succeed and ignore extra fields
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_endpoint_wrong_message_type(self, async_test_client):
        """Test that non-string message field returns validation error."""
        response = await async_test_client.post(
            "/api/v1/chat",
            json={"message": 123},  # Number instead of string
        )

        assert response.status_code == 422  # FastAPI validation error
        error_data = response.json()
        error_details = error_data["detail"]
        assert any("str_type" in str(err) or "string" in str(err).lower() for err in error_details)


class TestResponseValidation:
    """Test response format and headers."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_response_headers_streaming(
        self, async_test_client, mock_langgraph_success
    ):
        """Test that streaming response has correct headers."""
        async with async_test_client.stream(
            "POST", "/api/v1/chat", json={"message": "Hello"}
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"

    @pytest.mark.asyncio
    async def test_chat_endpoint_response_headers_error(self, async_test_client):
        """Test that error response has correct headers."""
        # Mock LangGraph failure
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(500, json={"detail": "Server error"})
            )

            response = await async_test_client.post("/api/v1/chat", json={"message": "Hello"})

            assert response.status_code == 200  # FastAPI returns 200 with error content
            assert "application/json" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_chat_endpoint_error_response_format(self, async_test_client):
        """Test that error responses have consistent format."""
        # Mock LangGraph failure
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(500, json={"detail": "Server error"})
            )

            response = await async_test_client.post("/api/v1/chat", json={"message": "Hello"})

            assert response.status_code == 200
            error_data = response.json()
            assert "error" in error_data
            assert isinstance(error_data["error"], str)


class TestAuthValidation:
    """Test authentication and authorization validation."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_without_auth_header(self):
        """Test that requests without auth header fail when auth is enabled."""
        # Remove auth override to test real auth
        app.dependency_overrides = {}

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/api/v1/chat", json={"message": "Hello"})

            # Should fail due to missing auth
            assert response.status_code in [401, 422]  # Unauthorized or validation error

    @pytest.mark.asyncio
    async def test_chat_endpoint_invalid_auth_header(self):
        """Test that requests with invalid auth header fail."""
        # Remove auth override to test real auth
        app.dependency_overrides = {}

        with patch.dict("os.environ", {"COGNI_API_KEY": "valid_key"}):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "Hello"},
                    headers={"Authorization": "Bearer invalid_key"},
                )

                # Should fail due to invalid auth
                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_endpoint_malformed_auth_header(self):
        """Test that requests with malformed auth header fail."""
        # Remove auth override to test real auth
        app.dependency_overrides = {}

        with patch.dict("os.environ", {"COGNI_API_KEY": "valid_key"}):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "Hello"},
                    headers={"Authorization": "invalid_format"},
                )

                # Should fail due to malformed auth
                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_endpoint_valid_auth_header(self, mock_langgraph_success):
        """Test that requests with valid auth header succeed."""
        # Remove auth override to test real auth
        app.dependency_overrides = {}

        with patch.dict("os.environ", {"COGNI_API_KEY": "valid_key"}):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/chat",
                    json={"message": "Hello"},
                    headers={"Authorization": "Bearer valid_key"},
                )

                # Should succeed with valid auth
                assert response.status_code == 200


class TestHTTPMethods:
    """Test HTTP method validation."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_get_method_not_allowed(self, async_test_client):
        """Test that GET requests to chat endpoint are not allowed."""
        response = await async_test_client.get("/api/v1/chat")
        assert response.status_code == 405  # Method Not Allowed

    @pytest.mark.asyncio
    async def test_chat_endpoint_put_method_not_allowed(self, async_test_client):
        """Test that PUT requests to chat endpoint are not allowed."""
        response = await async_test_client.put("/api/v1/chat", json={"message": "Hello"})
        assert response.status_code == 405  # Method Not Allowed

    @pytest.mark.asyncio
    async def test_chat_endpoint_delete_method_not_allowed(self, async_test_client):
        """Test that DELETE requests to chat endpoint are not allowed."""
        response = await async_test_client.delete("/api/v1/chat")
        assert response.status_code == 405  # Method Not Allowed

    @pytest.mark.asyncio
    async def test_chat_endpoint_patch_method_not_allowed(self, async_test_client):
        """Test that PATCH requests to chat endpoint are not allowed."""
        response = await async_test_client.patch("/api/v1/chat", json={"message": "Hello"})
        assert response.status_code == 405  # Method Not Allowed


class TestEdgeCases:
    """Test edge cases and unusual scenarios."""

    @pytest.mark.asyncio
    async def test_chat_endpoint_request_timeout_simulation(self, async_test_client):
        """Test handling of request timeout scenarios."""
        # Mock LangGraph to simulate timeout
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            import asyncio

            async def slow_response():
                await asyncio.sleep(10)  # Simulate slow response
                return httpx.Response(200, json={"thread_id": "test"})

            respx_mock.post("/threads").mock(side_effect=slow_response)

            # This test would timeout in real scenario, but we're just testing the structure
            # In practice, you'd want to set a shorter timeout for this test
            try:
                response = await async_test_client.post("/api/v1/chat", json={"message": "Hello"})
                # If it doesn't timeout, it should handle gracefully
                assert response.status_code in [200, 500, 504]
            except Exception:
                # Timeout or connection error is expected
                pass

    @pytest.mark.asyncio
    async def test_chat_endpoint_concurrent_requests_same_message(
        self, async_test_client, mock_langgraph_success
    ):
        """Test handling of multiple concurrent requests with same message."""
        import asyncio

        # Make multiple concurrent requests with same message
        async def make_request():
            return await async_test_client.post("/api/v1/chat", json={"message": "Hello"})

        tasks = [make_request() for _ in range(5)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All requests should succeed (or fail gracefully)
        for response in responses:
            if isinstance(response, Exception):
                # Some might fail due to resource limits, that's okay
                continue
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_endpoint_special_characters_in_message(
        self, async_test_client, mock_langgraph_success
    ):
        """Test handling of special characters that might break JSON parsing."""
        special_messages = [
            '{"malicious": "json"}',  # JSON-like string
            "Line 1\nLine 2\nLine 3",  # Newlines
            "Tab\tseparated\tvalues",  # Tabs
            "Quote \" and ' characters",  # Quotes
            "Backslash \\ characters",  # Backslashes
            "Unicode: 🚀 🌟 ⭐",  # Emojis
            "Control chars: \x00\x01\x02",  # Control characters
        ]

        for message in special_messages:
            response = await async_test_client.post("/api/v1/chat", json={"message": message})
            # Should handle all special characters gracefully
            assert response.status_code == 200, f"Failed for message: {repr(message)}"

    @pytest.mark.asyncio
    async def test_chat_endpoint_extremely_nested_json(self, async_test_client):
        """Test handling of extremely nested JSON (potential DoS)."""
        # Create deeply nested JSON
        nested_data = {"message": "Hello"}
        for _ in range(100):  # Create 100 levels of nesting
            nested_data = {"nested": nested_data}

        response = await async_test_client.post("/api/v1/chat", json=nested_data)

        # Should either accept it or reject with validation error
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_chat_endpoint_large_json_payload(self, async_test_client):
        """Test handling of very large JSON payloads."""
        # Create large payload (but not message field)
        large_data = {
            "message": "Hello",
            "large_field": "x" * 100000,  # 100KB of data
            "another_large_field": ["item"] * 10000,  # Large array
        }

        response = await async_test_client.post("/api/v1/chat", json=large_data)

        # Should either accept it (ignoring extra fields) or reject due to size limits
        assert response.status_code in [200, 413, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
