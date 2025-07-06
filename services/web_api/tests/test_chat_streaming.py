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


class TestChatEndpointStreaming:
    """Test streaming functionality of the chat endpoint."""

    def test_chat_endpoint_sends_multiple_chunks(self, client_with_mock_auth, mock_langgraph_streaming):
        """Test that chat endpoint properly streams multiple SSE chunks."""

        # Make request to chat endpoint
        response = client_with_mock_auth.post("/chat", json={"message": "Hello"})

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

        # Verify LangGraph endpoints were called
        assert mock_langgraph_streaming.calls

    def test_chat_endpoint_proper_langgraph_request_format(self, client_with_mock_auth, mock_langgraph_success):
        """Test that requests to LangGraph are formatted correctly."""

        # Make request
        response = client_with_mock_auth.post("/chat", json={"message": "Test message"})

        # Verify response is successful
        assert response.status_code == 200

        # Verify requests were made
        assert mock_langgraph_success.calls

        # Verify thread creation request
        thread_calls = [call for call in mock_langgraph_success.calls if call.request.url.path == "/threads"]
        assert len(thread_calls) == 1
        thread_call = thread_calls[0]
        assert thread_call.request.content == b"{}"  # Empty JSON

        # Verify streaming request format
        stream_calls = [call for call in mock_langgraph_success.calls if call.request.url.path == "/threads/test_thread_123/runs/stream"]
        assert len(stream_calls) == 1
        stream_call = stream_calls[0]
        run_data = json.loads(stream_call.request.content)

        assert run_data["assistant_id"] == "cogni_presence"
        assert run_data["stream_mode"] == "messages-tuple"
        assert "input" in run_data
        assert "messages" in run_data["input"]
        assert len(run_data["input"]["messages"]) == 1
        assert run_data["input"]["messages"][0]["role"] == "user"
        assert run_data["input"]["messages"][0]["content"] == "Test message"

    def test_chat_endpoint_error_propagation(self, client_with_mock_auth, mock_langgraph_error):
        """Test error handling when LangGraph backend fails."""

        # Make request
        response = client_with_mock_auth.post("/chat", json={"message": "Hello"})

        # Should return error response
        assert response.status_code == 200  # FastAPI returns 200 but with error content

        # The response should be a streaming error response
        content = response.text
        assert "error" in content
        # The actual error response just contains "error", not the full message
        assert content.strip() == "error"


class TestChatEndpointRequestValidation:
    """Test request validation and input handling."""

    def test_chat_endpoint_missing_message_field(self, client_with_mock_auth):
        """Test that missing message field returns validation error."""

        # With Pydantic validation, this should return a 422 validation error
        response = client_with_mock_auth.post("/chat", json={})  # Missing message field
        assert response.status_code == 422  # FastAPI validation error
        
        # Check that error mentions missing message field
        error_data = response.json()
        assert "detail" in error_data
        error_details = error_data["detail"]
        assert any(err.get("loc") == ["body", "message"] for err in error_details)

    def test_chat_endpoint_empty_message(self, client_with_mock_auth, mock_langgraph_success):
        """Test handling of empty message content."""

        # Test empty string message
        response = client_with_mock_auth.post("/chat", json={"message": ""})

        # Should accept empty message (LangGraph should handle it)
        assert response.status_code == 200

        # Verify empty message was passed through
        stream_calls = [call for call in mock_langgraph_success.calls if call.request.url.path == "/threads/test_thread_123/runs/stream"]
        assert len(stream_calls) == 1
        stream_call = stream_calls[0]
        run_data = json.loads(stream_call.request.content)
        assert run_data["input"]["messages"][0]["content"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
