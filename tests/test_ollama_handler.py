"""
Test the OllamaModelHandler implementation
"""

import unittest
from unittest.mock import patch, MagicMock

# Import the OllamaModelHandler from its new location
from infra_core.model_handlers.ollama_handler import OllamaModelHandler
from infra_core.model_handlers.base import BaseModelHandler


class TestOllamaModelHandler(unittest.TestCase):
    """Test the Ollama model handler with mocked API responses."""

    def test_inheritance(self):
        """Test that OllamaModelHandler inherits from BaseModelHandler."""
        handler = OllamaModelHandler()
        self.assertIsInstance(handler, BaseModelHandler)
        self.assertEqual(handler.supports_threads, False)
        self.assertEqual(handler.supports_streaming, True)

    def test_init_params(self):
        """Test initialization parameters."""
        # Test default parameters
        handler = OllamaModelHandler()
        self.assertEqual(handler.api_url, "http://localhost:11434/api")
        self.assertEqual(handler.default_model, "deepseek-coder")
        self.assertEqual(handler.timeout, 120)

        # Test custom parameters
        handler = OllamaModelHandler(
            api_url="http://custom-url:1234/api", default_model="mistral", timeout=60
        )
        self.assertEqual(handler.api_url, "http://custom-url:1234/api")
        self.assertEqual(handler.default_model, "mistral")
        self.assertEqual(handler.timeout, 60)

    @patch("requests.post")
    def test_create_chat_completion(self, mock_post):
        """Test the create_chat_completion method."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "deepseek-coder",
            "response": "This is a test response from Ollama",
            "done": True,
        }
        mock_post.return_value = mock_response

        # Create the handler and call method
        handler = OllamaModelHandler()
        response = handler.create_chat_completion(
            system_message="You are a helpful assistant",
            user_prompt="Hello, world!",
            temperature=0.5,
            max_tokens=100,
        )

        # Verify the request was sent to the correct endpoint
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:11434/api/generate")

        # Verify payload structure
        payload = kwargs["json"]
        self.assertEqual(payload["model"], "deepseek-coder")
        self.assertIn("System: You are a helpful assistant", payload["prompt"])
        self.assertIn("User: Hello, world!", payload["prompt"])
        self.assertEqual(payload["options"]["temperature"], 0.5)
        self.assertEqual(payload["options"]["num_predict"], 100)

        # Test response conversion to OpenAI format
        self.assertEqual(
            response["choices"][0]["message"]["content"], "This is a test response from Ollama"
        )

        # Test content extraction
        content = handler.extract_content(response)
        self.assertEqual(content, "This is a test response from Ollama")

    @patch("requests.post")
    def test_with_message_history(self, mock_post):
        """Test with message history."""
        # Create a mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "model": "deepseek-coder",
            "response": "This is a response with history",
            "done": True,
        }
        mock_post.return_value = mock_response

        # Create message history
        message_history = [
            {"role": "user", "content": "Previous message 1"},
            {"role": "assistant", "content": "Previous response 1"},
            {"role": "user", "content": "Previous message 2"},
            {"role": "assistant", "content": "Previous response 2"},
        ]

        # Create the handler and call method
        handler = OllamaModelHandler()
        response = handler.create_chat_completion(
            system_message="You are a helpful assistant",
            user_prompt="Continue the conversation",
            message_history=message_history,
        )

        # Verify payload structure includes history
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        prompt = payload["prompt"]

        # Check that the messages are in the correct order in the prompt
        self.assertIn("System: You are a helpful assistant", prompt)
        self.assertIn("User: Previous message 1", prompt)
        self.assertIn("Assistant: Previous response 1", prompt)
        self.assertIn("User: Previous message 2", prompt)
        self.assertIn("Assistant: Previous response 2", prompt)
        self.assertIn("User: Continue the conversation", prompt)

        # Verify the response was properly converted
        self.assertEqual(
            response["choices"][0]["message"]["content"], "This is a response with history"
        )

    def test_extract_content_error(self):
        """Test extract_content with invalid response."""
        handler = OllamaModelHandler()

        # Test with missing 'choices'
        invalid_response = {"not_choices": []}
        with self.assertRaises(ValueError):
            handler.extract_content(invalid_response)

        # Test with empty 'choices'
        invalid_response = {"choices": []}
        with self.assertRaises(ValueError):
            handler.extract_content(invalid_response)

        # Test with missing 'message'
        invalid_response = {"choices": [{"not_message": {}}]}
        with self.assertRaises(ValueError):
            handler.extract_content(invalid_response)


if __name__ == "__main__":
    unittest.main()
