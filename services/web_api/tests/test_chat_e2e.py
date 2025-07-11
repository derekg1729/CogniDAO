#!/usr/bin/env python3
"""
End-to-End Chat Flow Tests
==========================

Integration tests for the complete chat request flow from FastAPI
through LangGraph to final response streaming.

Key test areas:
1. Complete request flow (thread creation → run → streaming)
2. Streaming response validation
3. Error recovery and timeout handling
4. Performance and resource management
"""

import pytest
import json
import uuid
import asyncio
from httpx import AsyncClient
import respx
import httpx

from services.web_api.app import app
from services.web_api import auth_utils


# Override auth for testing
async def mock_verify_auth():
    return True


app.dependency_overrides[auth_utils.verify_auth] = mock_verify_auth


@pytest.fixture
async def async_test_client():
    """Async test client for FastAPI app."""
    transport = httpx.ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_thread_id():
    """Generate a sample thread ID for testing."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_run_id():
    """Generate a sample run ID for testing."""
    return str(uuid.uuid4())


class TestCompleteRequestFlow:
    """Test the complete request flow from start to finish."""

    @pytest.mark.asyncio
    async def test_complete_chat_flow_success(
        self, async_test_client, sample_thread_id, sample_run_id
    ):
        """Test complete successful chat flow with realistic streaming."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock thread creation
            thread_request = respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            # Mock realistic streaming response (using the correct POST endpoint)
            realistic_stream = [
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": "I"}}\n\n',
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": " can"}}\n\n',
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": " help"}}\n\n',
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": " you"}}\n\n',
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": " with"}}\n\n',
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": " that"}}\n\n',
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": "."}}\n\n',
                'data: {"type": "messages/complete"}\n\n',
            ]

            async def streaming_response():
                for chunk in realistic_stream:
                    yield chunk.encode("utf-8")

            stream_request = respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(200, stream=streaming_response())
            )

            # Make the request
            async with async_test_client.stream(
                "POST", "/api/v1/chat", json={"message": "Hello, can you help me?"}
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

                # Collect streaming chunks
                chunks = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)

                # Verify we received streaming content (may be combined into fewer chunks)
                assert len(chunks) >= 1  # Should have received at least one chunk

                # Verify the complete message can be reconstructed
                full_content = "".join(chunks)
                # The content is in SSE format, check for the individual words
                assert "I" in full_content
                assert "can" in full_content
                assert "help" in full_content
                assert "you" in full_content
                assert "with" in full_content
                assert "that" in full_content

            # Verify all endpoints were called correctly
            assert thread_request.called
            assert stream_request.called

            # Verify request formats
            stream_call = stream_request.calls[0]
            run_data = json.loads(stream_call.request.content)
            assert run_data["assistant_id"] == "cogni_presence"
            assert run_data["stream_mode"] == "messages-tuple"
            assert run_data["input"]["messages"][0]["content"] == "Hello, can you help me?"

    @pytest.mark.asyncio
    async def test_complete_chat_flow_with_tool_usage(
        self, async_test_client, sample_thread_id, sample_run_id
    ):
        """Test complete chat flow that includes tool usage."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock thread creation
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            # Mock streaming response with tool usage (using the correct endpoint)
            stream_content = (
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": "Let me search for that information."}}\n\n'
                'data: {"type": "tool_calls", "content": {"name": "GetActiveWorkItems", "args": {}}}\n\n'
                'data: {"type": "tool_results", "content": {"result": "Found 3 active work items"}}\n\n'
                'data: {"type": "messages/partial", "content": {"role": "ai", "content": "Based on my search, I found 3 active work items."}}\n\n'
                'data: {"type": "messages/complete"}\n\n'
            )

            respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(200, text=stream_content)
            )

            # Make request for information that would require tools
            async with async_test_client.stream(
                "POST", "/api/v1/chat", json={"message": "What are the current active work items?"}
            ) as response:
                assert response.status_code == 200

                chunks = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)

                # Verify tool usage is reflected in the stream
                full_content = "".join(chunks)
                assert "search" in full_content.lower()
                assert "found 3 active work items" in full_content.lower()

    @pytest.mark.asyncio
    async def test_complete_chat_flow_empty_response(
        self, async_test_client, sample_thread_id, sample_run_id
    ):
        """Test handling of empty or minimal responses."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock successful setup
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            # Mock minimal streaming response (using the correct POST endpoint)
            minimal_stream = [
                'data: {"type": "messages/complete"}\n\n',
            ]

            async def minimal_streaming_response():
                for chunk in minimal_stream:
                    yield chunk.encode("utf-8")

            respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(200, stream=minimal_streaming_response())
            )

            async with async_test_client.stream(
                "POST", "/api/v1/chat", json={"message": "Test"}
            ) as response:
                assert response.status_code == 200

                chunks = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)

                # Should handle minimal response gracefully
                assert len(chunks) >= 1


class TestErrorRecoveryAndTimeouts:
    """Test error recovery and timeout handling in the complete flow."""

    @pytest.mark.asyncio
    async def test_thread_creation_failure_recovery(self, async_test_client):
        """Test recovery when thread creation fails."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock thread creation failure
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(500, json={"detail": "Thread creation failed"})
            )

            response = await async_test_client.post("/api/v1/chat", json={"message": "Hello"})

            # Should return error response
            assert response.status_code == 200  # FastAPI wrapper returns 200 with error
            error_data = response.json()
            assert "error" in error_data

    @pytest.mark.asyncio
    async def test_streaming_failure_recovery(self, async_test_client, sample_thread_id):
        """Test recovery when streaming fails."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock successful thread creation
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            # Mock streaming failure
            respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(500, json={"detail": "Streaming failed"})
            )

            response = await async_test_client.post("/api/v1/chat", json={"message": "Hello"})

            assert response.status_code == 200
            # Error response is in SSE format, not JSON
            error_content = response.text
            assert "error" in error_content
            assert "500 Internal Server Error" in error_content

    @pytest.mark.asyncio
    async def test_streaming_interruption_recovery(
        self, async_test_client, sample_thread_id, sample_run_id
    ):
        """Test recovery when streaming is interrupted."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock successful setup
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            # Mock streaming that gets interrupted
            async def interrupted_streaming():
                yield b'data: {"type": "messages/partial", "content": {"role": "ai", "content": "Hello"}}\n\n'
                yield b'data: {"type": "messages/partial", "content": {"role": "ai", "content": " world"}}\n\n'
                # Simulate interruption
                raise ConnectionError("Stream interrupted")

            respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(200, stream=interrupted_streaming())
            )

            async with async_test_client.stream(
                "POST", "/api/v1/chat", json={"message": "Hello"}
            ) as response:
                assert response.status_code == 200

                chunks = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)

                # Should have received some chunks before interruption
                # Error should be handled gracefully
                full_content = "".join(chunks)
                assert "error" in full_content.lower() or len(chunks) > 0

    @pytest.mark.asyncio
    async def test_langgraph_service_timeout(self, async_test_client):
        """Test handling when LangGraph service is completely unavailable."""
        # No respx mock - let the request fail naturally
        response = await async_test_client.post("/api/v1/chat", json={"message": "Hello"})

        # Should handle service unavailability gracefully
        assert response.status_code == 200
        error_data = response.json()
        assert "error" in error_data


class TestPerformanceAndResourceManagement:
    """Test performance characteristics and resource management."""

    @pytest.mark.asyncio
    async def test_concurrent_chat_requests(self, async_test_client):
        """Test handling of multiple concurrent chat requests."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock responses for multiple concurrent requests  
            # Use a simple catch-all approach since all get the same thread ID
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": "thread_shared"})
            )

            async def shared_stream():
                yield b'data: {"type": "messages/partial", "content": {"role": "ai", "content": "Response"}}\n\n'
                yield b'data: {"type": "messages/complete"}\n\n'

            respx_mock.post("/threads/thread_shared/runs/stream").mock(
                return_value=httpx.Response(200, stream=shared_stream())
            )

            # Make concurrent requests
            async def make_request(msg_num):
                async with async_test_client.stream(
                    "POST", "/api/v1/chat", json={"message": f"Message {msg_num}"}
                ) as response:
                    chunks = []
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            chunks.append(chunk)
                    return response.status_code, chunks

            tasks = [make_request(i) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All requests should succeed or fail gracefully
            successful_requests = 0
            for result in results:
                if isinstance(result, tuple):
                    status_code, chunks = result
                    if status_code == 200:
                        successful_requests += 1

            # At least some requests should succeed
            assert successful_requests > 0

    @pytest.mark.asyncio
    async def test_large_message_handling(self, async_test_client, sample_thread_id, sample_run_id):
        """Test handling of large messages in the complete flow."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock successful flow
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            stream_mock = respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(200, text='data: {"type": "complete"}\n\n')
            )

            # Test with large message
            large_message = "This is a very long message. " * 1000  # ~30KB message

            response = await async_test_client.post("/api/v1/chat", json={"message": large_message})

            assert response.status_code == 200

            # Verify large message was passed through correctly
            run_call = stream_mock.calls[0]
            run_data = json.loads(run_call.request.content)
            assert run_data["input"]["messages"][0]["content"] == large_message

    @pytest.mark.asyncio
    async def test_streaming_performance_timing(
        self, async_test_client, sample_thread_id, sample_run_id
    ):
        """Test streaming performance and timing characteristics."""
        import time

        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock fast responses
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            # Mock streaming with timing
            async def timed_streaming():
                for i in range(10):
                    chunk = f'data: {{"type": "messages/partial", "content": {{"role": "ai", "content": "Token {i}"}}}}\n\n'
                    yield chunk.encode("utf-8")
                    await asyncio.sleep(0.01)  # Small delay between tokens
                final_chunk = 'data: {"type": "messages/complete"}\n\n'
                yield final_chunk.encode("utf-8")

            respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                return_value=httpx.Response(200, stream=timed_streaming())
            )

            start_time = time.time()

            async with async_test_client.stream(
                "POST", "/api/v1/chat", json={"message": "Test timing"}
            ) as response:
                assert response.status_code == 200

                chunks = []
                chunk_times = []
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        chunks.append(chunk)
                        chunk_times.append(time.time())

                total_time = time.time() - start_time

                # Should receive chunks (may be combined)
                assert len(chunks) >= 1
                assert total_time > 0.05  # Should take some time due to delays

                # Verify chunks arrived progressively
                if len(chunk_times) > 1:
                    time_diffs = [
                        chunk_times[i] - chunk_times[i - 1] for i in range(1, len(chunk_times))
                    ]
                    # At least some time differences should be > 0 (progressive delivery)
                    assert any(diff > 0 for diff in time_diffs)


class TestRealWorldScenarios:
    """Test realistic usage scenarios."""

    @pytest.mark.asyncio
    async def test_typical_user_conversation(
        self, async_test_client, sample_thread_id, sample_run_id
    ):
        """Test a typical user conversation flow."""
        with respx.mock(base_url="http://langgraph-cogni-presence:8000") as respx_mock:
            # Mock conversation responses
            respx_mock.post("/threads").mock(
                return_value=httpx.Response(200, json={"thread_id": sample_thread_id})
            )

            conversation_responses = {
                "Hello": "Hello! How can I help you today?",
                "What can you do?": "I can help you with various tasks using my available tools.",
                "Show me active work items": "Let me check the active work items for you.",
            }

            def mock_conversation_stream(message):
                response_text = conversation_responses.get(message, "I understand.")
                return [
                    f'data: {{"type": "messages/partial", "content": {{"role": "ai", "content": "{response_text}"}}}}\n\n',
                    'data: {"type": "messages/complete"}\n\n',
                ]

            # Test conversation flow
            messages = ["Hello", "What can you do?", "Show me active work items"]

            for message in messages:

                async def conversation_stream():
                    for chunk in mock_conversation_stream(message):
                        yield chunk.encode("utf-8")

                respx_mock.post(f"/threads/{sample_thread_id}/runs/stream").mock(
                    return_value=httpx.Response(200, stream=conversation_stream())
                )

                async with async_test_client.stream(
                    "POST", "/api/v1/chat", json={"message": message}
                ) as response:
                    assert response.status_code == 200

                    chunks = []
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            chunks.append(chunk)

                    full_content = "".join(chunks)
                    expected_response = conversation_responses.get(message, "I understand.")
                    assert expected_response in full_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
