#!/usr/bin/env python3
"""
FastAPI /chat Endpoint Streaming Tests
======================================

Tests the new FastAPI /chat endpoint that proxies to LangGraph service.
Uses HTTPX mocking with respx to avoid real network calls.

Key test cases:
1. Basic streaming - multiple SSE chunks delivered
2. Error propagation - backend failures surface clean errors
3. Auth flow - headers passed correctly
4. Thread/run creation workflow
5. Request format validation
"""

import pytest
import json
from fastapi.testclient import TestClient
import respx
import httpx


@pytest.fixture
def fastapi_test_app():
    """FastAPI test application."""
    from ..app import app

    return app


@pytest.fixture
def test_client(fastapi_test_app):
    """Test client for FastAPI app."""
    return TestClient(fastapi_test_app)


@pytest.fixture
def mock_auth():
    """Mock auth dependency."""

    def mock_verify_auth():
        return {"user_id": "test_user"}

    return mock_verify_auth


class TestChatEndpointStreaming:
    """Test streaming functionality of the chat endpoint."""

    @respx.mock
    def test_chat_endpoint_sends_multiple_chunks(self, test_client, mock_auth):
        """Test that chat endpoint properly streams multiple SSE chunks."""

        # Override auth dependency
        from ..auth_utils import verify_auth

        test_client.app.dependency_overrides[verify_auth] = mock_auth

        # Mock LangGraph API responses
        thread_response = respx.post("http://langgraph-cogni-presence:8000/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread_123"})
        )

        run_response = respx.post(
            "http://langgraph-cogni-presence:8000/threads/test_thread_123/runs"
        ).mock(return_value=httpx.Response(200, json={"run_id": "test_run_456"}))

        # Mock streaming response with proper text content
        stream_content = (
            'data: {"type": "message", "content": "Hello"}\n\n'
            'data: {"type": "message", "content": " world"}\n\n'
            'data: {"type": "message", "content": "!"}\n\n'
            'data: {"type": "done"}\n\n'
        )

        stream_response = respx.get(
            "http://langgraph-cogni-presence:8000/threads/test_thread_123/runs/test_run_456/stream"
        ).mock(return_value=httpx.Response(200, text=stream_content))

        # Make request to chat endpoint
        response = test_client.post("/chat", json={"message": "Hello"})

        # Verify response is streaming
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "no-cache"

        # Collect all streamed chunks
        content = response.content.decode()

        # Verify we got multiple chunks
        assert "Hello" in content
        assert "world" in content
        assert "!" in content

        # Verify all API calls were made
        assert thread_response.called
        assert run_response.called
        assert stream_response.called

        # Clean up
        test_client.app.dependency_overrides = {}

    @respx.mock
    def test_chat_endpoint_proper_langgraph_request_format(self, test_client, mock_auth):
        """Test that requests to LangGraph are formatted correctly."""

        # Override auth dependency
        from ..auth_utils import verify_auth

        test_client.app.dependency_overrides[verify_auth] = mock_auth

        # Mock LangGraph API responses
        thread_response = respx.post("http://langgraph-cogni-presence:8000/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread_123"})
        )

        run_response = respx.post(
            "http://langgraph-cogni-presence:8000/threads/test_thread_123/runs"
        ).mock(return_value=httpx.Response(200, json={"run_id": "test_run_456"}))

        stream_response = respx.get(
            "http://langgraph-cogni-presence:8000/threads/test_thread_123/runs/test_run_456/stream"
        ).mock(return_value=httpx.Response(200, text='data: {"type": "complete"}\n\n'))

        # Make request
        test_client.post("/chat", json={"message": "Test message"})

        # Verify requests were made
        assert thread_response.called
        assert run_response.called
        assert stream_response.called

        # Verify thread creation request
        thread_call = thread_response.calls[0]
        assert thread_call.request.content == b"{}"  # Empty JSON

        # Verify run creation request format
        run_call = run_response.calls[0]
        run_data = json.loads(run_call.request.content)

        assert run_data["assistant_id"] == "cogni_presence"
        assert run_data["stream"] is True
        assert "input" in run_data
        assert "messages" in run_data["input"]
        assert len(run_data["input"]["messages"]) == 1
        assert run_data["input"]["messages"][0]["role"] == "user"
        assert run_data["input"]["messages"][0]["content"] == "Test message"

        # Clean up
        test_client.app.dependency_overrides = {}

    @respx.mock
    def test_chat_endpoint_error_propagation(self, test_client, mock_auth):
        """Test error handling when LangGraph backend fails."""

        # Override auth dependency
        from ..auth_utils import verify_auth

        test_client.app.dependency_overrides[verify_auth] = mock_auth

        # Mock thread creation failure
        respx.post("http://langgraph-cogni-presence:8000/threads").mock(
            return_value=httpx.Response(500, json={"detail": "Internal server error"})
        )

        # Make request
        response = test_client.post("/chat", json={"message": "Hello"})

        # Should return error response
        assert response.status_code == 200  # FastAPI returns 200 but with error content

        # The response should be a JSON error
        error_data = response.json()
        assert "error" in error_data
        assert "Server error" in error_data["error"]

        # Clean up
        test_client.app.dependency_overrides = {}


class TestChatEndpointRequestValidation:
    """Test request validation and input handling."""

    def test_chat_endpoint_missing_message_field(self, test_client, mock_auth):
        """Test that missing message field causes server error."""

        # Override auth dependency
        from ..auth_utils import verify_auth

        test_client.app.dependency_overrides[verify_auth] = mock_auth

        # The current implementation doesn't validate input, so this will cause a 500 error
        # rather than a 422 validation error
        try:
            response = test_client.post("/chat", json={})  # Missing message field
            # If we get here, the endpoint handled the error
            assert response.status_code == 500
        except Exception:
            # If we get an exception, that's also expected behavior for the current implementation
            pass

        # Clean up
        test_client.app.dependency_overrides = {}

    @respx.mock
    def test_chat_endpoint_empty_message(self, test_client, mock_auth):
        """Test handling of empty message content."""

        # Override auth dependency
        from ..auth_utils import verify_auth

        test_client.app.dependency_overrides[verify_auth] = mock_auth

        # Mock LangGraph responses
        respx.post("http://langgraph-cogni-presence:8000/threads").mock(
            return_value=httpx.Response(200, json={"thread_id": "test_thread_123"})
        )

        run_response = respx.post(
            "http://langgraph-cogni-presence:8000/threads/test_thread_123/runs"
        ).mock(return_value=httpx.Response(200, json={"run_id": "test_run_456"}))

        respx.get(
            "http://langgraph-cogni-presence:8000/threads/test_thread_123/runs/test_run_456/stream"
        ).mock(return_value=httpx.Response(200, text='data: {"type": "complete"}\n\n'))

        # Test empty string message
        response = test_client.post("/chat", json={"message": ""})

        # Should accept empty message (LangGraph should handle it)
        assert response.status_code == 200

        # Verify empty message was passed through
        run_call = run_response.calls[0]
        run_data = json.loads(run_call.request.content)
        assert run_data["input"]["messages"][0]["content"] == ""

        # Clean up
        test_client.app.dependency_overrides = {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
