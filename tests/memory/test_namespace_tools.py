"""
Tests for namespace management tools (create and list).

This test suite validates the namespace creation and listing functionality,
ensuring proper validation, error handling, and database operations.
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from infra_core.memory_system.tools.agent_facing.create_namespace_tool import (
    CreateNamespaceInput,
    create_namespace_tool,
)
from infra_core.memory_system.tools.agent_facing.dolt_namespace_tool import (
    ListNamespacesInput,
    NamespaceInfo,
    list_namespaces_tool,
)


class TestNamespaceTools:
    """Test namespace creation and listing tools."""

    @pytest.fixture
    def mock_memory_bank(self):
        """Create a mock StructuredMemoryBank for namespace operations."""
        bank = MagicMock()

        # Mock the dolt_reader and dolt_writer
        bank.dolt_reader = MagicMock()
        bank.dolt_writer = MagicMock()

        # Mock branch query
        bank.dolt_reader._execute_query.return_value = [
            {"branch": "schema-update/namespace-test-1750046075"}
        ]

        return bank

    @pytest.fixture
    def sample_namespaces_data(self):
        """Sample namespace data for testing."""
        return [
            {
                "id": "legacy",
                "name": "Legacy",
                "slug": "legacy",
                "owner_id": "system",
                "created_at": datetime(2024, 1, 1, 12, 0, 0),
                "description": "Legacy namespace for pre-migration memory blocks",
                "is_active": True,
            },
            {
                "id": "cogni-project-management",
                "name": "Cogni Project Management",
                "slug": "cogni-project-management",
                "owner_id": "system",
                "created_at": datetime(2024, 6, 16, 10, 0, 0),
                "description": "Namespace for Cogni project management tasks",
                "is_active": True,
            },
        ]


class TestCreateNamespaceTool(TestNamespaceTools):
    """Test the create_namespace_tool functionality."""

    def test_create_namespace_success(self, mock_memory_bank):
        """Test successful namespace creation."""
        # Mock no existing namespace
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],  # Branch query
            [],  # No existing namespace
        ]

        # Mock successful insert
        mock_memory_bank.dolt_writer._execute_update.return_value = 1

        input_data = CreateNamespaceInput(
            id="test-namespace", name="Test Namespace", description="A test namespace"
        )

        result = create_namespace_tool(input_data, mock_memory_bank)

        assert result.success is True
        assert result.namespace_id == "test-namespace"
        assert "Successfully created namespace 'test-namespace'" in result.message
        assert result.active_branch == "test-branch"
        assert result.error is None

        # Verify the SQL insert was called correctly
        mock_memory_bank.dolt_writer._execute_update.assert_called_once()
        call_args = mock_memory_bank.dolt_writer._execute_update.call_args
        sql_query = call_args[0][0]
        sql_params = call_args[0][1]

        assert "INSERT INTO namespaces" in sql_query
        assert sql_params[0] == "test-namespace"  # id
        assert sql_params[1] == "Test Namespace"  # name
        assert sql_params[2] == "test-namespace"  # slug (defaults to id)
        assert sql_params[3] == "system"  # owner_id (default)
        assert sql_params[5] == "A test namespace"  # description
        assert sql_params[6] is True  # is_active (default)

    def test_create_namespace_with_custom_fields(self, mock_memory_bank):
        """Test namespace creation with all custom fields."""
        # Mock no existing namespace
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],  # Branch query
            [],  # No existing namespace
        ]

        # Mock successful insert
        mock_memory_bank.dolt_writer._execute_update.return_value = 1

        input_data = CreateNamespaceInput(
            id="custom-namespace",
            name="Custom Namespace",
            slug="custom-slug",
            owner_id="user-123",
            description="Custom description",
            is_active=False,
        )

        result = create_namespace_tool(input_data, mock_memory_bank)

        assert result.success is True
        assert result.namespace_id == "custom-namespace"

        # Verify custom fields were used
        call_args = mock_memory_bank.dolt_writer._execute_update.call_args
        sql_params = call_args[0][1]

        assert sql_params[0] == "custom-namespace"  # id
        assert sql_params[1] == "Custom Namespace"  # name
        assert sql_params[2] == "custom-slug"  # slug
        assert sql_params[3] == "user-123"  # owner_id
        assert sql_params[5] == "Custom description"  # description
        assert sql_params[6] is False  # is_active

    def test_create_namespace_slug_defaults_to_id(self, mock_memory_bank):
        """Test that slug defaults to id when not provided."""
        # Mock no existing namespace
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],
            [],
        ]

        mock_memory_bank.dolt_writer._execute_update.return_value = 1

        input_data = CreateNamespaceInput(id="test-namespace-123", name="Test Namespace")

        result = create_namespace_tool(input_data, mock_memory_bank)

        assert result.success is True

        # Verify slug was set to id
        call_args = mock_memory_bank.dolt_writer._execute_update.call_args
        sql_params = call_args[0][1]
        assert sql_params[2] == "test-namespace-123"  # slug should equal id

    def test_create_namespace_already_exists(self, mock_memory_bank):
        """Test error when namespace already exists."""
        # Mock existing namespace found
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],  # Branch query
            [{"id": "existing-namespace"}],  # Existing namespace found
        ]

        input_data = CreateNamespaceInput(id="existing-namespace", name="Existing Namespace")

        result = create_namespace_tool(input_data, mock_memory_bank)

        assert result.success is False
        assert result.namespace_id is None
        assert "Namespace 'existing-namespace' already exists" in result.message
        assert result.error is not None

        # Verify no insert was attempted
        mock_memory_bank.dolt_writer._execute_update.assert_not_called()

    def test_create_namespace_insert_fails(self, mock_memory_bank):
        """Test error when database insert fails."""
        # Mock no existing namespace
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],
            [],
        ]

        # Mock failed insert (0 rows affected)
        mock_memory_bank.dolt_writer._execute_update.return_value = 0

        input_data = CreateNamespaceInput(id="test-namespace", name="Test Namespace")

        result = create_namespace_tool(input_data, mock_memory_bank)

        assert result.success is False
        assert result.namespace_id is None
        assert "no rows affected" in result.message
        assert result.error is not None

    def test_create_namespace_database_exception(self, mock_memory_bank):
        """Test error handling when database operation raises exception."""
        # Mock database exception
        mock_memory_bank.dolt_reader._execute_query.side_effect = Exception(
            "Database connection failed"
        )

        input_data = CreateNamespaceInput(id="test-namespace", name="Test Namespace")

        result = create_namespace_tool(input_data, mock_memory_bank)

        assert result.success is False
        assert result.namespace_id is None
        assert "Failed to create namespace" in result.message
        assert "Database connection failed" in result.error

    def test_create_namespace_input_validation(self):
        """Test input validation for CreateNamespaceInput."""
        # Test valid input
        valid_input = CreateNamespaceInput(id="valid-namespace", name="Valid Namespace")
        assert valid_input.id == "valid-namespace"
        assert valid_input.name == "Valid Namespace"
        assert valid_input.slug == "valid-namespace"  # Should default to id
        assert valid_input.owner_id == "system"  # Should use default
        assert valid_input.is_active is True  # Should use default

        # Test with custom slug
        custom_slug_input = CreateNamespaceInput(id="test-id", name="Test Name", slug="custom-slug")
        assert custom_slug_input.slug == "custom-slug"

        # Test required fields validation
        with pytest.raises(ValueError):
            CreateNamespaceInput(name="Missing ID")  # Missing required id

        with pytest.raises(ValueError):
            CreateNamespaceInput(id="missing-name")  # Missing required name


class TestListNamespacesTool(TestNamespaceTools):
    """Test the list_namespaces_tool functionality."""

    def test_list_namespaces_success(self, mock_memory_bank, sample_namespaces_data):
        """Test successful namespace listing."""
        # Mock database query returning sample data
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],  # Branch query
            sample_namespaces_data,  # Namespaces query
        ]

        input_data = ListNamespacesInput()
        result = list_namespaces_tool(input_data, mock_memory_bank)

        assert result.success is True
        assert result.total_count == 2
        assert len(result.namespaces) == 2
        assert result.active_branch == "test-branch"
        assert result.error is None
        assert "Found 2 namespaces" in result.message

        # Verify namespace data
        legacy_ns = next(ns for ns in result.namespaces if ns.id == "legacy")
        assert legacy_ns.name == "Legacy"
        assert legacy_ns.slug == "legacy"
        assert legacy_ns.owner_id == "system"
        assert legacy_ns.is_active is True

        project_ns = next(ns for ns in result.namespaces if ns.id == "cogni-project-management")
        assert project_ns.name == "Cogni Project Management"
        assert project_ns.description == "Namespace for Cogni project management tasks"

    def test_list_namespaces_empty_result(self, mock_memory_bank):
        """Test listing when no namespaces exist."""
        # Mock empty result
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],  # Branch query
            [],  # Empty namespaces query
        ]

        input_data = ListNamespacesInput()
        result = list_namespaces_tool(input_data, mock_memory_bank)

        assert result.success is True
        assert result.total_count == 0
        assert len(result.namespaces) == 0
        assert "No namespaces found" in result.message

    def test_list_namespaces_database_exception(self, mock_memory_bank):
        """Test error handling when database query fails."""
        # Mock database exception
        mock_memory_bank.dolt_reader._execute_query.side_effect = Exception("Query failed")

        input_data = ListNamespacesInput()
        result = list_namespaces_tool(input_data, mock_memory_bank)

        assert result.success is False
        assert result.total_count == 0
        assert len(result.namespaces) == 0
        assert "Failed to list namespaces" in result.message
        assert "Query failed" in result.error

    def test_list_namespaces_sql_query_structure(self, mock_memory_bank, sample_namespaces_data):
        """Test that the SQL query has the correct structure."""
        mock_memory_bank.dolt_reader._execute_query.side_effect = [
            [{"branch": "test-branch"}],
            sample_namespaces_data,
        ]

        input_data = ListNamespacesInput()
        list_namespaces_tool(input_data, mock_memory_bank)

        # Verify the SQL query was called correctly
        calls = mock_memory_bank.dolt_reader._execute_query.call_args_list

        # Second call should be the namespaces query
        namespaces_query_call = calls[1]
        sql_query = namespaces_query_call[0][0]

        # Verify query structure
        assert "SELECT" in sql_query
        assert "FROM namespaces" in sql_query
        assert "ORDER BY name" in sql_query
        assert "id" in sql_query
        assert "name" in sql_query
        assert "slug" in sql_query
        assert "owner_id" in sql_query
        assert "created_at" in sql_query
        assert "description" in sql_query
        assert "COALESCE(is_active, TRUE)" in sql_query

    def test_namespace_info_model(self):
        """Test NamespaceInfo model validation."""
        # Test valid namespace info
        namespace_info = NamespaceInfo(
            id="test-namespace",
            name="Test Namespace",
            slug="test-slug",
            owner_id="user-123",
            created_at=datetime.now(),
            description="Test description",
            is_active=True,
        )

        assert namespace_info.id == "test-namespace"
        assert namespace_info.name == "Test Namespace"
        assert namespace_info.slug == "test-slug"
        assert namespace_info.owner_id == "user-123"
        assert namespace_info.description == "Test description"
        assert namespace_info.is_active is True

        # Test with minimal required fields
        minimal_namespace = NamespaceInfo(
            id="minimal",
            name="Minimal",
            slug="minimal",
            owner_id="system",
            created_at=datetime.now(),
        )

        assert minimal_namespace.description is None
        assert minimal_namespace.is_active is True  # Default value

    def test_list_namespaces_input_model(self):
        """Test ListNamespacesInput model (should accept no parameters)."""
        # Should work with no parameters
        input_data = ListNamespacesInput()
        assert input_data is not None

        # Should also work with empty dict
        input_data2 = ListNamespacesInput(**{})
        assert input_data2 is not None
