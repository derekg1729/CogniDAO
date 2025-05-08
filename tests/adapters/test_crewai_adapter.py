"""
Tests for the CrewAI adapter package structure and imports.

These tests verify that:
1. The package can be imported
2. Required classes are exported
3. Version information is available

Note: Currently skipped as the CrewAI adapter implementation is not yet complete.
"""

import pytest
from cogni_adapters import __version__
from cogni_adapters.crewai import CogniMemoryStorage


@pytest.mark.skip(reason="CrewAI adapter implementation not yet complete")
def test_package_version():
    """Test that version information is available."""
    assert __version__ == "0.1.0"


@pytest.mark.skip(reason="CrewAI adapter implementation not yet complete")
def test_crewai_adapter_imports():
    """Test that all required classes are exported."""
    # These will raise ImportError if the classes aren't properly exported
    assert CogniMemoryStorage is not None


@pytest.mark.skip(reason="CrewAI adapter implementation not yet complete")
def test_crewai_adapter_all():
    """Test that __all__ contains all expected exports."""
    from cogni_adapters.crewai import __all__

    expected_exports = {
        "CogniMemoryStorage",
    }
    assert set(__all__) == expected_exports
