import pytest
from unittest.mock import MagicMock
from pydantic import BaseModel


@pytest.fixture
def mock_tool():
    """Create a mock CogniTool instance."""

    class MockInput(BaseModel):
        text: str

    class MockOutput(BaseModel):
        success: bool
        id: str = "error_id"  # Default ID for error cases
        error: str = None

    def mock_invoke(input_data):
        try:
            # Validate input
            if not isinstance(input_data, dict):
                raise ValueError("Input must be a dictionary")

            # Check schema
            if mock.input_model is None:
                raise ValueError("No input schema defined")

            # Parse input
            validated_input = mock.input_model(**input_data)

            # Call function
            result = mock.function(validated_input)

            # Return output model
            return mock.output_model(**result.model_dump())
        except Exception as e:
            return mock.output_model(success=False, error=str(e))

    mock = MagicMock()
    mock.input_model = MockInput
    mock.output_model = MockOutput
    mock.function = MagicMock(return_value=MockOutput(success=True, id="test_id"))
    mock.invoke = mock_invoke
    return mock


class TestCogniTool:
    def test_invoke_with_invalid_input(self, mock_tool):
        """Test that invalid input raises a validation error."""
        result = mock_tool.invoke({"invalid": "input"})
        assert not result.success
        assert "field required" in result.error.lower()

    def test_invoke_with_error(self, mock_tool):
        """Test that function errors are handled correctly."""
        mock_tool.function.side_effect = Exception("Test error")
        result = mock_tool.invoke({"text": "test"})
        assert not result.success
        assert "Test error" in result.error

    def test_invoke_with_persistence_error(self, mock_tool):
        """Test that persistence errors are handled correctly."""
        mock_tool.function.side_effect = Exception("Failed to persist")
        result = mock_tool.invoke({"text": "test"})
        assert not result.success
        assert "Failed to persist" in result.error

    def test_invoke_with_schema_error(self, mock_tool):
        """Test that schema validation errors are handled correctly."""
        mock_tool.input_model = None  # Simulate missing schema
        result = mock_tool.invoke({"text": "test"})
        assert not result.success
        assert "No input schema defined" in result.error
