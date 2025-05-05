"""
Simple test to verify model handlers can be imported correctly.
"""


def test_import_model_handlers():
    """Test that model handlers can be imported without errors."""
    from infra_core.model_handlers import (
        BaseModelHandler,
        OpenAIModelHandler,
        OllamaModelHandler,
    )

    # Basic assertions to test the imports worked
    assert issubclass(OpenAIModelHandler, BaseModelHandler)
    assert issubclass(OllamaModelHandler, BaseModelHandler)

    # Verify handler attributes
    openai_handler = OpenAIModelHandler()
    assert openai_handler.supports_threads is True

    ollama_handler = OllamaModelHandler()
    assert ollama_handler.supports_threads is False

    print("All model handler imports successful!")


if __name__ == "__main__":
    test_import_model_handlers()
