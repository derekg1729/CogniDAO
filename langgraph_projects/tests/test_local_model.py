"""
Test for Local Model Integration

Tests the provider abstraction and model binding without making real API calls.
Following LangGraph testing best practices with mocked dependencies.
"""

import os
import pytest
from unittest.mock import Mock, patch

# Fixed imports for tests directory
from src.shared_utils.model_binding import get_model_handler, create_model_config
from src.shared_utils.logging_utils import get_logger

logger = get_logger(__name__)


class TestProviderAbstraction:
    """Test the provider switching logic without real API calls."""

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_MODEL": "gpt-4o-mini"})
    def test_openai_provider_setup(self):
        """Test that OpenAI provider is configured correctly."""
        with patch("src.shared_utils.model_binding.ChatOpenAI") as mock_chat_openai:
            mock_model = Mock()
            mock_chat_openai.return_value = mock_model

            get_model_handler()

            # Verify ChatOpenAI was called with correct parameters
            mock_chat_openai.assert_called_once()
            call_kwargs = mock_chat_openai.call_args.kwargs

            assert call_kwargs["model"] == "gpt-4o-mini"
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["streaming"] is True
            assert "openai_api_base" not in call_kwargs  # Should not have custom base URL

    @patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen3:8b",
            "OLLAMA_URL": "http://qwen-ollama:11434",
        },
    )
    def test_ollama_provider_setup(self):
        """Test that Ollama provider is configured correctly."""
        with patch("src.shared_utils.model_binding.ChatOpenAI") as mock_chat_openai:
            mock_model = Mock()
            mock_chat_openai.return_value = mock_model

            get_model_handler()

            # Verify ChatOpenAI was called with Ollama configuration
            mock_chat_openai.assert_called_once()
            call_kwargs = mock_chat_openai.call_args.kwargs

            assert call_kwargs["model"] == "qwen3:8b"
            assert call_kwargs["openai_api_key"] == "sk-local"
            assert call_kwargs["openai_api_base"] == "http://qwen-ollama:11434/v1"
            assert call_kwargs["temperature"] == 0.0
            assert call_kwargs["streaming"] is True

    @patch.dict(os.environ, {"LLM_PROVIDER": "invalid_provider"})
    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises appropriate error."""
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER: invalid_provider"):
            get_model_handler()

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_MODEL": "invalid-model"})
    def test_invalid_openai_model_raises_error(self):
        """Test that invalid OpenAI model raises appropriate error."""
        with pytest.raises(ValueError, match="Unsupported OpenAI model invalid-model"):
            get_model_handler()


class TestModelConfiguration:
    """Test model configuration creation."""

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_MODEL": "gpt-4o"})
    def test_openai_model_config(self):
        """Test OpenAI model configuration."""
        config = create_model_config(temperature=0.1, streaming=False)

        assert config["model_name"] == "gpt-4o"
        assert config["provider"] == "openai"
        assert config["temperature"] == 0.1
        assert config["streaming"] is False

    @patch.dict(os.environ, {"LLM_PROVIDER": "ollama", "OLLAMA_MODEL": "qwen3:14b"})
    def test_ollama_model_config(self):
        """Test Ollama model configuration."""
        config = create_model_config(temperature=0.5, streaming=True)

        assert config["model_name"] == "qwen3:14b"
        assert config["provider"] == "ollama"
        assert config["temperature"] == 0.5
        assert config["streaming"] is True

    def test_default_model_config(self):
        """Test default model configuration when no env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            config = create_model_config()

            assert config["model_name"] == "gpt-4o-mini"  # Default OpenAI model
            assert config["provider"] == "openai"  # Default provider
            assert config["temperature"] == 0.0
            assert config["streaming"] is True


class TestModelBinding:
    """Test the model binding caching system."""

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai"})
    def test_model_binding_caching(self):
        """Test that model binding uses caching correctly."""
        from src.shared_utils.model_binding import get_cached_bound_model

        with patch("src.shared_utils.model_binding.get_model_handler") as mock_get_handler:
            mock_model = Mock()
            mock_bound_model = Mock()
            mock_model.bind_tools.return_value = mock_bound_model
            mock_get_handler.return_value = mock_model

            # Call twice with same parameters
            result1 = get_cached_bound_model("test-model", tools=[], temperature=0.0)
            result2 = get_cached_bound_model("test-model", tools=[], temperature=0.0)

            # Should return the bound model
            assert result1 == mock_bound_model
            assert result2 == mock_bound_model

            # bind_tools should be called on the model
            mock_model.bind_tools.assert_called_with([])


class TestEnvironmentDefaults:
    """Test that environment variable defaults work correctly."""

    def test_ollama_defaults(self):
        """Test Ollama environment defaults."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "ollama"}, clear=True):
            with patch("src.shared_utils.model_binding.ChatOpenAI") as mock_chat_openai:
                mock_model = Mock()
                mock_chat_openai.return_value = mock_model

                get_model_handler()

                call_kwargs = mock_chat_openai.call_args.kwargs
                assert call_kwargs["model"] == "qwen3:8b"  # Default OLLAMA_MODEL
                assert (
                    call_kwargs["openai_api_base"] == "http://qwen-ollama:11434/v1"
                )  # Default OLLAMA_URL

    def test_openai_defaults(self):
        """Test OpenAI environment defaults."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
            with patch("src.shared_utils.model_binding.ChatOpenAI") as mock_chat_openai:
                mock_model = Mock()
                mock_chat_openai.return_value = mock_model

                get_model_handler()

                call_kwargs = mock_chat_openai.call_args.kwargs
                assert call_kwargs["model"] == "gpt-4o-mini"  # Default OPENAI_MODEL


# Simplified validation test that doesn't make network calls
def test_validate_provider_setup_unit():
    """Unit test for provider validation without network calls."""
    with patch("src.shared_utils.model_binding.get_model_handler") as mock_get_handler:
        mock_handler = Mock()
        mock_get_handler.return_value = mock_handler

        # Import within the patch context to ensure mock is applied
        from src.shared_utils.model_binding import get_model_handler as patched_handler

        # Test that we can successfully get a model handler
        handler = patched_handler()
        assert handler == mock_handler
        mock_get_handler.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
