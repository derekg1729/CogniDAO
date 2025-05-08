"""
Shared test fixtures for adapter tests.

This module provides fixtures that will be used across multiple test files
in the adapters test suite.
"""

import pytest
from unittest.mock import MagicMock

from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


@pytest.fixture(params=["mock", "real"])
def memory_bank(request):
    """Create a memory bank instance.

    Args:
        request: pytest fixture request object containing the parameter

    Returns:
        Either a mock StructuredMemoryBank or a real instance based on the parameter.
    """
    if request.param == "mock":
        return MagicMock(spec=StructuredMemoryBank)
    else:
        # TODO: Implement real bank creation when needed
        pytest.skip("Real bank implementation not yet available")
