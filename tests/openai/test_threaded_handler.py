import sys
import os
import unittest
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from infra_core.openai_handler import create_thread, thread_completion


class TestThreadedHandler(unittest.TestCase):
    """Tests for the thread-based OpenAI handler functions."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Mock OpenAI client
        self.mock_client = MagicMock()
        
        # Mock thread creation
        self.mock_thread = MagicMock()
        self.mock_thread.id = "thread_123456"
        self.mock_client.beta.threads.create.return_value = self.mock_thread
        
        # Mock assistant creation
        self.mock_assistant = MagicMock()
        self.mock_assistant.id = "asst_123456"
        self.mock_client.beta.assistants.create.return_value = self.mock_assistant
        
        # Mock thread message creation
        self.mock_message = MagicMock()
        self.mock_message.id = "msg_123456"
        self.mock_client.beta.threads.messages.create.return_value = self.mock_message
        
        # Mock run creation and retrieval
        self.mock_run = MagicMock()
        self.mock_run.id = "run_123456"
        self.mock_run.status = "completed"
        self.mock_client.beta.threads.runs.create.return_value = self.mock_run
        self.mock_client.beta.threads.runs.retrieve.return_value = self.mock_run
        
        # Mock message listing
        self.mock_messages = MagicMock()
        self.mock_assistant_message = MagicMock()
        self.mock_assistant_message.role = "assistant"
        self.mock_assistant_message.content = [MagicMock()]
        self.mock_assistant_message.content[0].text.value = "This is a test response"
        self.mock_messages.data = [self.mock_assistant_message]
        self.mock_client.beta.threads.messages.list.return_value = self.mock_messages
    
    def test_create_thread(self):
        """Test creating a thread and assistant."""
        # Call the function
        thread_id, assistant_id = create_thread(
            client=self.mock_client,
            instructions="Test instructions",
            model="gpt-4"
        )
        
        # Verify thread was created
        self.mock_client.beta.threads.create.assert_called_once()
        
        # Verify assistant was created with correct parameters
        self.mock_client.beta.assistants.create.assert_called_once_with(
            name="ThreadedCompletion",
            instructions="Test instructions",
            model="gpt-4"
        )
        
        # Verify correct IDs are returned
        self.assertEqual(thread_id, "thread_123456")
        self.assertEqual(assistant_id, "asst_123456")
    
    def test_thread_completion(self):
        """Test sending a message to a thread and getting a response."""
        # Call the function
        response = thread_completion(
            client=self.mock_client,
            thread_id="thread_123456",
            assistant_id="asst_123456",
            user_prompt="Test prompt"
        )
        
        # Verify message was added to thread
        self.mock_client.beta.threads.messages.create.assert_called_once_with(
            thread_id="thread_123456",
            role="user",
            content="Test prompt"
        )
        
        # Verify run was created
        self.mock_client.beta.threads.runs.create.assert_called_once_with(
            thread_id="thread_123456",
            assistant_id="asst_123456"
        )
        
        # Verify run status was checked
        self.mock_client.beta.threads.runs.retrieve.assert_called_with(
            thread_id="thread_123456",
            run_id="run_123456"
        )
        
        # Verify messages were listed
        self.mock_client.beta.threads.messages.list.assert_called_once_with(
            thread_id="thread_123456",
            order="desc",
            limit=1
        )
        
        # Verify response format matches create_completion
        expected_response = {
            "choices": [
                {
                    "message": {
                        "content": "This is a test response"
                    }
                }
            ]
        }
        self.assertEqual(response, expected_response)
    
    def test_thread_completion_polling(self):
        """Test polling for completion when run is not immediately completed."""
        # Set up run to be in progress, then completed
        run_in_progress = MagicMock()
        run_in_progress.id = "run_123456"
        run_in_progress.status = "in_progress"
        
        run_completed = MagicMock()
        run_completed.id = "run_123456"
        run_completed.status = "completed"
        
        # Return different status on first and second call
        self.mock_client.beta.threads.runs.retrieve.side_effect = [
            run_in_progress, run_completed
        ]
        
        # Mock time.sleep to avoid waiting
        with patch('time.sleep') as mock_sleep:
            response = thread_completion(
                client=self.mock_client,
                thread_id="thread_123456",
                assistant_id="asst_123456",
                user_prompt="Test prompt"
            )
            
            # Verify sleep was called (polling)
            mock_sleep.assert_called_once()
            
            # Verify retrieve was called multiple times
            self.assertEqual(self.mock_client.beta.threads.runs.retrieve.call_count, 2)
    
    def test_thread_completion_error(self):
        """Test error handling when run fails."""
        # Set up run to fail
        failed_run = MagicMock()
        failed_run.id = "run_123456"
        failed_run.status = "failed"
        self.mock_client.beta.threads.runs.retrieve.return_value = failed_run
        
        # Mock time.sleep to avoid waiting
        with patch('time.sleep'):
            # Expect ValueError to be raised
            with self.assertRaises(ValueError) as context:
                thread_completion(
                    client=self.mock_client,
                    thread_id="thread_123456",
                    assistant_id="asst_123456",
                    user_prompt="Test prompt"
                )
            
            # Verify error message
            self.assertIn("failed", str(context.exception))
    
    def test_thread_completion_no_assistant_message(self):
        """Test handling when no assistant message is found."""
        # Set up empty message list
        empty_messages = MagicMock()
        empty_messages.data = []
        self.mock_client.beta.threads.messages.list.return_value = empty_messages
        
        # Call the function
        response = thread_completion(
            client=self.mock_client,
            thread_id="thread_123456",
            assistant_id="asst_123456",
            user_prompt="Test prompt"
        )
        
        # Verify empty response is returned
        expected_response = {
            "choices": [
                {
                    "message": {
                        "content": ""
                    }
                }
            ]
        }
        self.assertEqual(response, expected_response)


if __name__ == "__main__":
    unittest.main()

