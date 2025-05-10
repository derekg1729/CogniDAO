import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from typing import List, Dict

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import functions to test
from legacy_logseq.openai_handler import (
    initialize_openai_client,
    create_completion,
    extract_content,
)

# Mock OpenAI class if needed, otherwise use MagicMock directly
# from openai import OpenAI # Not strictly needed if we mock the instance


class TestOpenAIHandler(unittest.TestCase):
    """Tests for the standard OpenAI handler functions."""

    def setUp(self):
        """Set up test environment before each test."""
        # Mock the OpenAI client instance
        self.mock_client = MagicMock()

        # Mock the response object structure expected from client.chat.completions.create
        self.mock_completion_response = MagicMock()
        # Define a structure that response.model_dump() would return
        self.mock_dump = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello there!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
        }
        self.mock_completion_response.model_dump.return_value = self.mock_dump
        self.mock_client.chat.completions.create.return_value = self.mock_completion_response

    # --- Tests for initialize_openai_client ---

    @patch("legacy_logseq.openai_handler.Secret")
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_initialize_client_with_secret(self, MockOpenAI, MockSecret):
        """Test initializing client using Prefect Secret."""
        mock_secret_instance = MockSecret.load.return_value
        mock_secret_instance.get.return_value = "test_secret_key"

        client = initialize_openai_client.fn()

        MockSecret.load.assert_called_once_with("OPENAI_API_KEY")
        mock_secret_instance.get.assert_called_once()
        MockOpenAI.assert_called_once_with(api_key="test_secret_key")
        self.assertIsNotNone(client)  # Check if a client object is returned

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test_env_key"}, clear=True)
    @patch("legacy_logseq.openai_handler.Secret")
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_initialize_client_with_env(self, MockOpenAI, MockSecret):
        """Test initializing client using environment variable as fallback."""
        # Make Secret loading fail
        MockSecret.load.side_effect = Exception("Failed to load secret")

        client = initialize_openai_client.fn()

        MockSecret.load.assert_called_once_with("OPENAI_API_KEY")
        MockOpenAI.assert_called_once_with(api_key="test_env_key")
        self.assertIsNotNone(client)

    @patch.dict(os.environ, {}, clear=True)  # No env var
    @patch("legacy_logseq.openai_handler.Secret")
    def test_initialize_client_no_key(self, MockSecret):
        """Test that ValueError is raised if no API key is found."""
        MockSecret.load.side_effect = Exception("Failed to load secret")

        with self.assertRaises(ValueError) as context:
            initialize_openai_client.fn()
        self.assertIn("OpenAI API key not found", str(context.exception))

    # --- Tests for create_completion ---

    def test_create_completion_no_history(self):
        """Test create_completion without message history."""
        system_msg = "You are a test bot."
        user_prompt = "Hello bot!"

        # Call the function using .fn() to bypass Prefect task runner for direct call
        create_completion.fn(
            client=self.mock_client,
            system_message=system_msg,
            user_prompt=user_prompt,
            model="gpt-test",
            temperature=0.5,
        )

        # Verify the structure of the 'messages' argument passed to OpenAI API
        expected_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ]

        self.mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-test",
            messages=expected_messages,
            temperature=0.5,
            max_tokens=None,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )

    def test_create_completion_with_history(self):
        """Test create_completion with message history."""
        system_msg = "You are a helpful assistant."
        user_prompt = "What's the weather?"
        history: List[Dict[str, str]] = [
            {"role": "user", "content": "Hi there!"},
            {"role": "assistant", "content": "Hello! How can I help?"},
        ]

        # Call the function using .fn()
        create_completion.fn(
            client=self.mock_client,
            system_message=system_msg,
            user_prompt=user_prompt,
            message_history=history,
            model="gpt-test-hist",
            temperature=0.6,
        )

        # Verify the structure of the 'messages' argument
        expected_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "Hi there!"},
            {"role": "assistant", "content": "Hello! How can I help?"},
            {"role": "user", "content": "What's the weather?"},
        ]

        self.mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-test-hist",
            messages=expected_messages,
            temperature=0.6,
            max_tokens=None,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
        )

    def test_create_completion_system_message_dict(self):
        """Test create_completion when system_message is already a dict."""
        system_msg = {"role": "system", "content": "System dict test."}
        user_prompt = "Test prompt."

        create_completion.fn(
            client=self.mock_client, system_message=system_msg, user_prompt=user_prompt
        )

        expected_messages = [system_msg, {"role": "user", "content": user_prompt}]

        # Check only the messages argument for simplicity
        call_args, call_kwargs = self.mock_client.chat.completions.create.call_args
        self.assertEqual(call_kwargs["messages"], expected_messages)

    # --- Tests for extract_content ---

    def test_extract_content_success(self):
        """Test successful extraction of content."""
        # Use the mock response structure defined in setUp
        content = extract_content.fn(self.mock_dump)
        self.assertEqual(content, "Hello there!")

    def test_extract_content_missing_key(self):
        """Test error handling when a key is missing."""
        bad_response = {"choices": [{"message": {}}]}  # Missing 'content'
        with self.assertRaises(ValueError) as context:
            extract_content.fn(bad_response)
        self.assertIn("Could not extract content", str(context.exception))

    def test_extract_content_empty_choices(self):
        """Test error handling with empty choices list."""
        bad_response = {"choices": []}
        with self.assertRaises(ValueError) as context:
            extract_content.fn(bad_response)
        self.assertIn("Could not extract content", str(context.exception))


if __name__ == "__main__":
    unittest.main()
