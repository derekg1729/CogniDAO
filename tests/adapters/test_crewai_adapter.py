"""
Tests for the CrewAI adapter package structure and imports.

These tests verify that:
1. The package can be imported
2. Required classes are exported
3. Version information is available
"""

from cogni_adapters import __version__
from cogni_adapters.crewai import (
    CogniMemoryStorage,
    SaveMemoryBlockTool,
    QueryMemoryBlockTool,
)


def test_package_version():
    """Test that version information is available."""
    assert __version__ == "0.1.0"


def test_crewai_adapter_imports():
    """Test that all required classes are exported."""
    # These will raise ImportError if the classes aren't properly exported
    assert CogniMemoryStorage is not None
    assert SaveMemoryBlockTool is not None
    assert QueryMemoryBlockTool is not None


def test_crewai_adapter_all():
    """Test that __all__ contains all expected exports."""
    from cogni_adapters.crewai import __all__

    expected_exports = {
        "CogniMemoryStorage",
        "SaveMemoryBlockTool",
        "QueryMemoryBlockTool",
    }
    assert set(__all__) == expected_exports
