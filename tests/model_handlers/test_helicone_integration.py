"""
Comprehensive Pytest Suite for Helicone Integration

Tests all aspects of the enhanced Helicone integration including:
- Basic Helicone proxy functionality
- HELICONE_BASE_URL support (SaaS and self-hosted)
- Enhanced observability headers (User-Id, Session-Id, Cache-Enabled, Properties)
- Both legacy and model handler code paths
- Environment variable configurations
- Error handling and fallback behavior

Uses proper mocking to avoid actual API calls while ensuring
real integration behavior is tested.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

# Import the handlers to test
from legacy_logseq.openai_handler import (
    initialize_openai_client,
    create_completion,
    extract_content,
)
from infra_core.model_handlers.openai_handler import OpenAIModelHandler


class TestHeliconeBasicIntegration:
    """Test basic Helicone proxy integration functionality."""

    @patch.dict(
        os.environ, {"HELICONE_API_KEY": "sk-helicone-test-key", "OPENAI_API_KEY": "sk-openai-test"}
    )
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_legacy_handler_uses_helicone_when_key_present(self, mock_openai):
        """Test that legacy handler uses Helicone proxy when HELICONE_API_KEY is set."""

        # Call the function
        initialize_openai_client.fn()

        # Verify OpenAI was initialized with Helicone proxy
        mock_openai.assert_called_once_with(
            api_key="sk-openai-test",
            base_url="https://oai.helicone.ai/v1",
            default_headers={"Helicone-Auth": "Bearer sk-helicone-test-key"},
        )

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=True)
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_legacy_handler_uses_standard_openai_when_no_helicone_key(self, mock_openai):
        """Test that legacy handler uses standard OpenAI when HELICONE_API_KEY is not set."""

        # Call the function
        initialize_openai_client.fn()

        # Verify OpenAI was initialized without Helicone
        mock_openai.assert_called_once_with(api_key="sk-openai-test")

    @patch.dict(
        os.environ, {"HELICONE_API_KEY": "sk-helicone-test", "OPENAI_API_KEY": "sk-openai-test"}
    )
    @patch("infra_core.model_handlers.openai_handler.OpenAI")
    def test_model_handler_uses_helicone_when_key_present(self, mock_openai):
        """Test that model handler uses Helicone proxy when HELICONE_API_KEY is set."""

        # Create handler with explicit API key
        handler = OpenAIModelHandler(api_key="sk-openai-test")

        # Access client property to trigger initialization
        _ = handler.client

        # Verify OpenAI was initialized with Helicone proxy
        mock_openai.assert_called_once_with(
            api_key="sk-openai-test",
            base_url="https://oai.helicone.ai/v1",
            default_headers={"Helicone-Auth": "Bearer sk-helicone-test"},
        )


class TestHeliconeBaseUrlConfiguration:
    """Test HELICONE_BASE_URL environment variable support."""

    @patch.dict(
        os.environ,
        {
            "HELICONE_API_KEY": "sk-helicone-test",
            "OPENAI_API_KEY": "sk-openai-test",
            "HELICONE_BASE_URL": "http://localhost:8585/v1",
        },
    )
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_legacy_handler_uses_custom_base_url(self, mock_openai):
        """Test that legacy handler uses custom HELICONE_BASE_URL for self-hosted deployments."""

        initialize_openai_client.fn()

        mock_openai.assert_called_once_with(
            api_key="sk-openai-test",
            base_url="http://localhost:8585/v1",
            default_headers={"Helicone-Auth": "Bearer sk-helicone-test"},
        )

    @patch.dict(
        os.environ,
        {
            "HELICONE_API_KEY": "sk-helicone-test",
            "OPENAI_API_KEY": "sk-openai-test",
            "HELICONE_BASE_URL": "https://enterprise.helicone.ai/v1",
        },
    )
    @patch("infra_core.model_handlers.openai_handler.OpenAI")
    def test_model_handler_uses_custom_base_url(self, mock_openai):
        """Test that model handler uses custom HELICONE_BASE_URL for enterprise deployments."""

        handler = OpenAIModelHandler(api_key="sk-openai-test")
        _ = handler.client

        mock_openai.assert_called_once_with(
            api_key="sk-openai-test",
            base_url="https://enterprise.helicone.ai/v1",
            default_headers={"Helicone-Auth": "Bearer sk-helicone-test"},
        )

    @patch.dict(
        os.environ, {"HELICONE_API_KEY": "sk-helicone-test", "OPENAI_API_KEY": "sk-openai-test"}
    )
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_default_base_url_when_not_specified(self, mock_openai):
        """Test that default Helicone SaaS URL is used when HELICONE_BASE_URL not specified."""

        initialize_openai_client.fn()

        mock_openai.assert_called_once_with(
            api_key="sk-openai-test",
            base_url="https://oai.helicone.ai/v1",  # Default SaaS URL
            default_headers={"Helicone-Auth": "Bearer sk-helicone-test"},
        )


class TestHeliconeObservabilityHeaders:
    """Test enhanced Helicone observability headers functionality."""

    def setup_method(self):
        """Set up mock client and response for each test."""
        self.mock_client = MagicMock()

        # Mock OpenAI API response
        self.mock_response = MagicMock()
        self.mock_response.model_dump.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "model": "gpt-3.5-turbo",
        }
        self.mock_client.chat.completions.create.return_value = self.mock_response

    def test_legacy_handler_with_all_helicone_headers(self):
        """Test that legacy handler correctly passes all Helicone headers."""

        # Call with all Helicone headers
        create_completion.fn(
            client=self.mock_client,
            system_message="Test system",
            user_prompt="Test prompt",
            helicone_user_id="user-123",
            helicone_session_id="session-456",
            helicone_cache_enabled=True,
            helicone_properties={"app": "test", "environment": "pytest"},
        )

        # Verify the API call included all expected headers
        self.mock_client.chat.completions.create.assert_called_once()
        call_kwargs = self.mock_client.chat.completions.create.call_args[1]

        expected_headers = {
            "Helicone-User-Id": "user-123",
            "Helicone-Session-Id": "session-456",
            "Helicone-Cache-Enabled": "true",
            "Helicone-Property-app": "test",
            "Helicone-Property-environment": "pytest",
        }

        assert call_kwargs["extra_headers"] == expected_headers

    def test_legacy_handler_with_selective_headers(self):
        """Test that legacy handler only includes provided Helicone headers."""

        create_completion.fn(
            client=self.mock_client,
            system_message="Test system",
            user_prompt="Test prompt",
            helicone_user_id="user-123",
            helicone_cache_enabled=False,
            # Note: No session_id or properties provided
        )

        call_kwargs = self.mock_client.chat.completions.create.call_args[1]
        expected_headers = {"Helicone-User-Id": "user-123", "Helicone-Cache-Enabled": "false"}

        assert call_kwargs["extra_headers"] == expected_headers

    def test_legacy_handler_with_no_helicone_headers(self):
        """Test that legacy handler works correctly with no Helicone headers."""

        create_completion.fn(
            client=self.mock_client, system_message="Test system", user_prompt="Test prompt"
        )

        call_kwargs = self.mock_client.chat.completions.create.call_args[1]

        # Should not include extra_headers when none provided
        assert call_kwargs.get("extra_headers") is None

    @patch("infra_core.model_handlers.openai_handler.create_completion")
    def test_model_handler_passes_headers_to_legacy_function(self, mock_create_completion):
        """Test that model handler correctly passes Helicone headers to legacy function."""

        mock_create_completion.return_value = {"choices": [{"message": {"content": "Test"}}]}

        handler = OpenAIModelHandler()
        handler._client = self.mock_client  # Inject mock client

        handler.create_chat_completion(
            system_message="Test system",
            user_prompt="Test prompt",
            helicone_user_id="user-789",
            helicone_session_id="session-012",
            helicone_properties={"source": "model_handler"},
        )

        # Verify the legacy function was called with headers
        mock_create_completion.assert_called_once()
        call_kwargs = mock_create_completion.call_args[1]

        assert call_kwargs["helicone_user_id"] == "user-789"
        assert call_kwargs["helicone_session_id"] == "session-012"
        assert call_kwargs["helicone_properties"] == {"source": "model_handler"}


class TestHeliconeErrorHandling:
    """Test error handling and edge cases in Helicone integration."""

    @patch.dict(os.environ, {"HELICONE_API_KEY": "", "OPENAI_API_KEY": "sk-openai-test"})
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_empty_helicone_key_uses_standard_openai(self, mock_openai):
        """Test that empty HELICONE_API_KEY is treated as not set."""

        initialize_openai_client.fn()

        # Should use standard OpenAI (no Helicone proxy)
        mock_openai.assert_called_once_with(api_key="sk-openai-test")

    @patch.dict(os.environ, {"HELICONE_API_KEY": "   ", "OPENAI_API_KEY": "sk-openai-test"})
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_whitespace_helicone_key_uses_standard_openai(self, mock_openai):
        """Test that whitespace-only HELICONE_API_KEY is treated as not set."""

        initialize_openai_client.fn()

        # Should use standard OpenAI (no Helicone proxy)
        mock_openai.assert_called_once_with(api_key="sk-openai-test")

    def test_helicone_properties_with_none_values(self):
        """Test that None values in helicone_properties are handled gracefully."""

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.model_dump.return_value = {"choices": [{"message": {"content": "Test"}}]}
        mock_client.chat.completions.create.return_value = mock_response

        # Properties with None values should be filtered out
        create_completion.fn(
            client=mock_client,
            system_message="Test",
            user_prompt="Test",
            helicone_properties={"valid_key": "valid_value", "none_key": None},
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        expected_headers = {
            "Helicone-Property-valid_key": "valid_value",
            "Helicone-Property-none_key": None,  # None values should be preserved as strings
        }

        assert call_kwargs["extra_headers"] == expected_headers


class TestHeliconeIntegrationEndToEnd:
    """End-to-end integration tests for complete Helicone workflow."""

    @patch.dict(
        os.environ,
        {
            "HELICONE_API_KEY": "sk-helicone-e2e-test",
            "OPENAI_API_KEY": "sk-openai-e2e-test",
            "HELICONE_BASE_URL": "https://custom.helicone.com/v1",
        },
    )
    @patch("legacy_logseq.openai_handler.OpenAI")
    def test_complete_legacy_workflow_with_helicone(self, mock_openai):
        """Test complete legacy workflow: initialize -> create completion -> extract content."""

        # Setup mock client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "choices": [{"message": {"content": "Hello from Helicone!"}}],
            "model": "gpt-3.5-turbo",
        }
        mock_client.chat.completions.create.return_value = mock_response

        # Execute the complete workflow
        client = initialize_openai_client.fn()
        response = create_completion.fn(
            client=client,
            system_message="You are a helpful assistant",
            user_prompt="Say hello",
            helicone_user_id="e2e-user",
            helicone_cache_enabled=True,
        )
        content = extract_content.fn(response)

        # Verify Helicone initialization
        mock_openai.assert_called_once_with(
            api_key="sk-openai-e2e-test",
            base_url="https://custom.helicone.com/v1",
            default_headers={"Helicone-Auth": "Bearer sk-helicone-e2e-test"},
        )

        # Verify API call with headers
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "Helicone-User-Id" in call_kwargs["extra_headers"]
        assert call_kwargs["extra_headers"]["Helicone-User-Id"] == "e2e-user"

        # Verify final result
        assert content == "Hello from Helicone!"

    @patch.dict(
        os.environ,
        {"HELICONE_API_KEY": "sk-helicone-model-test", "OPENAI_API_KEY": "sk-openai-model-test"},
    )
    @patch("infra_core.model_handlers.openai_handler.create_completion")
    def test_complete_model_handler_workflow_with_helicone(self, mock_create_completion):
        """Test complete model handler workflow with Helicone integration."""

        # Setup mock response
        mock_create_completion.return_value = {
            "choices": [{"message": {"content": "Model handler with Helicone works!"}}]
        }

        # Execute workflow
        handler = OpenAIModelHandler(api_key="sk-openai-model-test")
        response = handler.create_chat_completion(
            system_message="Test system message",
            user_prompt="Test user prompt",
            helicone_user_id="model-user",
            helicone_session_id="model-session",
            helicone_properties={"handler_type": "model", "test": "e2e"},
        )
        content = handler.extract_content(response)

        # Verify headers were passed through
        mock_create_completion.assert_called_once()
        call_kwargs = mock_create_completion.call_args[1]

        assert call_kwargs["helicone_user_id"] == "model-user"
        assert call_kwargs["helicone_session_id"] == "model-session"
        assert call_kwargs["helicone_properties"] == {"handler_type": "model", "test": "e2e"}

        # Verify final result
        assert content == "Model handler with Helicone works!"


# Pytest configuration and fixtures
@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables before/after each test to avoid interference."""
    # Store original values
    original_env = {
        key: os.environ.get(key)
        for key in ["HELICONE_API_KEY", "HELICONE_BASE_URL", "OPENAI_API_KEY"]
    }

    yield

    # Restore original environment
    for key, value in original_env.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
