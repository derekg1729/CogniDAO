"""
Conftest for LangGraph Tests

Provides mocks for dependencies that aren't available in the langgraph environment
to prevent autouse fixtures in the root conftest.py from failing.
"""

import sys
import pytest
from unittest.mock import MagicMock


# Mock mysql.connector before any imports to prevent ModuleNotFoundError
if "mysql" not in sys.modules:
    mysql_mock = MagicMock()
    mysql_connector_mock = MagicMock()
    mysql_connector_mock.connect = MagicMock()
    mysql_mock.connector = mysql_connector_mock
    sys.modules["mysql"] = mysql_mock
    sys.modules["mysql.connector"] = mysql_connector_mock


# Mock infra_core modules before any imports
if "infra_core" not in sys.modules:
    infra_core_mock = MagicMock()
    memory_system_mock = MagicMock()
    link_manager_mock = MagicMock()

    # Create a mock LinkManager class for isinstance checks
    class MockLinkManager:
        pass

    link_manager_mock.LinkManager = MockLinkManager
    memory_system_mock.link_manager = link_manager_mock
    infra_core_mock.memory_system = memory_system_mock

    sys.modules["infra_core"] = infra_core_mock
    sys.modules["infra_core.memory_system"] = memory_system_mock
    sys.modules["infra_core.memory_system.link_manager"] = link_manager_mock
    sys.modules["infra_core.memory_system.structured_memory_bank"] = MagicMock()
    sys.modules["infra_core.memory_system.sql_link_manager"] = MagicMock()


@pytest.fixture
def mock_mcp_client():
    """
    Simple mock MCP client for langgraph tests that need it.
    """
    mock_client = MagicMock()
    mock_client.get_tools.return_value = []
    return mock_client
