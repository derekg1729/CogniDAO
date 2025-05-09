import sys
import os
import unittest
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from langchain.schema import HumanMessage, AIMessage, SystemMessage

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the FastAPI app and models
from legacy_logseq.legacy_cogni_api import app, send_message, verify_auth  # Import verify_auth
from infra_core.models import HistoryMessage  # Import HistoryMessage


# Define a simple async generator for mocking send_message results
async def mock_async_generator(*args, **kwargs):
    yield "mock response chunk 1"
    yield "mock response chunk 2"


# Define a mock for the ChatOpenAI model
class MockChatOpenAI:
    def __init__(self, *args, **kwargs):
        pass  # Ignore constructor args

    # Mock the agenerate method which send_message calls
    agenerate = AsyncMock(return_value=None)  # We only care about the input messages


# --- Test Dependency Override ---
def override_verify_auth():
    """Override dependency to bypass actual auth logic."""
    return True


class TestCogniAPI(unittest.TestCase):
    """Tests for the Cogni FastAPI application endpoints and logic."""

    # REMOVED @patch decorator from setUp
    def setUp(self):
        """Set up test client and mock dependencies."""
        # Apply the dependency override for verify_auth
        app.dependency_overrides[verify_auth] = override_verify_auth
        self.client = TestClient(app)
        # No need to keep mock_verify_auth reference anymore

    def tearDown(self):
        """Clean up dependency overrides after tests."""
        app.dependency_overrides = {}

    # --- Tests for /chat endpoint (stream_chat function) ---

    @patch("legacy_logseq.legacy_cogni_api.send_message")  # Simpler patch
    def test_chat_endpoint_no_history(self, mock_send_message):
        """Test POST /chat endpoint without history."""
        # Configure mock inside the test
        mock_send_message.return_value = mock_async_generator()

        payload = {"message": "Hello"}
        response = self.client.post("/chat", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        # Check the content streamed back (optional, depends on mock_async_generator)
        self.assertEqual(response.text, "mock response chunk 1mock response chunk 2")

        # Verify send_message was called correctly
        mock_send_message.assert_called_once_with("Hello", None)

    @patch("legacy_logseq.legacy_cogni_api.send_message")  # Simpler patch
    def test_chat_endpoint_with_history(self, mock_send_message):
        """Test POST /chat endpoint with history."""
        # Configure mock inside the test
        mock_send_message.return_value = mock_async_generator()

        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
        ]
        payload = {"message": "Second message", "message_history": history}
        response = self.client.post("/chat", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")

        # Verify send_message was called correctly - Expect HistoryMessage objects now
        expected_history_objects = [
            HistoryMessage(role="user", content="First message"),
            HistoryMessage(role="assistant", content="First response"),
        ]
        mock_send_message.assert_called_once_with("Second message", expected_history_objects)

    # No *args needed now as setUp doesn't receive mocks
    def test_chat_endpoint_missing_message(self):
        """Test POST /chat endpoint with missing message field."""
        payload = {"message_history": []}  # Missing 'message'
        response = self.client.post("/chat", json=payload)
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        # Check error details (optional) - Check for message field error specifically
        self.assertIn("detail", response.json())
        # Check that the detail list contains an error for the message field
        error_details = response.json()["detail"]
        message_error_found = any(
            err.get("loc") == ["body", "message"] and err.get("type") == "missing"
            for err in error_details
        )
        self.assertTrue(
            message_error_found, "Validation error for missing 'message' field not found"
        )


# --- Tests for send_message function ---
# Use IsolatedAsyncioTestCase for async function testing
class TestSendMessageFunction(unittest.IsolatedAsyncioTestCase):
    @patch(
        "legacy_logseq.legacy_cogni_api.ChatOpenAI", new=MockChatOpenAI
    )  # Replace ChatOpenAI with our mock
    @patch(
        "legacy_logseq.legacy_cogni_api.AsyncIteratorCallbackHandler"
    )  # Mock the callback handler
    async def test_send_message_constructs_correct_lc_messages_no_history(
        self, MockCallback, *args
    ):
        """Verify send_message calls agenerate with correct messages (no history)."""
        # We don't care about the generator output here, just the call to agenerate
        async for _ in send_message(message="Test Query", history=None):
            pass  # Consume the generator

        # Assert that agenerate was called with the correct messages list
        # expected_lc_messages = [HumanMessage(content="Test Query")] # F841: Unused variable
        MockChatOpenAI.agenerate.assert_called_once()
        call_args, call_kwargs = MockChatOpenAI.agenerate.call_args
        # Need to compare content carefully as objects won't be identical
        self.assertEqual(len(call_kwargs["messages"][0]), 1)
        self.assertIsInstance(call_kwargs["messages"][0][0], HumanMessage)
        self.assertEqual(call_kwargs["messages"][0][0].content, "Test Query")
        # Reset mock for other tests
        MockChatOpenAI.agenerate.reset_mock()

    @patch("legacy_logseq.legacy_cogni_api.ChatOpenAI", new=MockChatOpenAI)
    @patch("legacy_logseq.legacy_cogni_api.AsyncIteratorCallbackHandler")
    async def test_send_message_constructs_correct_lc_messages_with_history(
        self, MockCallback, *args
    ):
        """Verify send_message calls agenerate with correct messages (with history)."""
        history = [
            {"role": "system", "content": "You are Cogni."},
            {"role": "user", "content": "First q"},
            {"role": "assistant", "content": "First a"},
        ]
        async for _ in send_message(message="Second q", history=history):
            pass

        expected_lc_messages = [
            SystemMessage(content="You are Cogni."),
            HumanMessage(content="First q"),
            AIMessage(content="First a"),
            HumanMessage(content="Second q"),
        ]
        MockChatOpenAI.agenerate.assert_called_once()
        call_args, call_kwargs = MockChatOpenAI.agenerate.call_args
        called_messages = call_kwargs["messages"][0]

        self.assertEqual(len(called_messages), len(expected_lc_messages))
        for i, msg in enumerate(expected_lc_messages):
            self.assertIsInstance(called_messages[i], type(msg))
            self.assertEqual(called_messages[i].content, msg.content)

        MockChatOpenAI.agenerate.reset_mock()

    @patch("legacy_logseq.legacy_cogni_api.ChatOpenAI", new=MockChatOpenAI)
    @patch("legacy_logseq.legacy_cogni_api.AsyncIteratorCallbackHandler")
    async def test_send_message_handles_invalid_history_items(self, MockCallback, *args):
        """Verify send_message skips invalid history entries."""
        history = [
            {"role": "user"},  # Missing content
            {"content": "Blah"},  # Missing role
            {"role": "invalid_role", "content": "Invalid role"},
            {"role": "assistant", "content": "Valid assistant msg"},
        ]
        async for _ in send_message(message="Final q", history=history):
            pass

        expected_lc_messages = [
            AIMessage(content="Valid assistant msg"),  # Only the valid history message
            HumanMessage(content="Final q"),
        ]
        MockChatOpenAI.agenerate.assert_called_once()
        call_args, call_kwargs = MockChatOpenAI.agenerate.call_args
        called_messages = call_kwargs["messages"][0]

        self.assertEqual(len(called_messages), len(expected_lc_messages))
        for i, msg in enumerate(expected_lc_messages):
            self.assertIsInstance(called_messages[i], type(msg))
            self.assertEqual(called_messages[i].content, msg.content)

        MockChatOpenAI.agenerate.reset_mock()


if __name__ == "__main__":
    unittest.main()
