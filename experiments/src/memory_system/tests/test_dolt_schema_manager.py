"""
Tests for Dolt schema management functionality.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from experiments.src.memory_system.dolt_schema_manager import (
    register_schema,
    register_all_metadata_schemas,
    get_schema,
    list_available_schemas
)

# Import schemas from the new structure
from experiments.src.memory_system.schemas.metadata import (
    ProjectMetadata,
    TaskMetadata,
    DocMetadata,
    KnowledgeMetadata
)
from experiments.src.memory_system.schemas.registry import (
    validate_metadata,
    get_available_node_types
)

# Patch the Dolt class
DOLT_PATCH_TARGET = 'experiments.src.memory_system.dolt_schema_manager.Dolt'

class TestDoltSchemaManager:
    """Tests for Dolt schema management functionality."""
    
    @pytest.fixture
    def mock_dolt(self):
        """Create a mock Dolt instance."""
        with patch(DOLT_PATCH_TARGET) as MockDolt:
            mock_repo = MagicMock()
            MockDolt.return_value = mock_repo
            
            # Mock the branch method to return the current branch
            mock_repo.branch.return_value = 'main'
            
            # Mock the sql method to return a successful result
            mock_repo.sql.return_value = {'rows': []}
            
            yield mock_repo
    
    def test_register_schema(self, mock_dolt):
        """Test registering a schema definition."""
        # Create a sample schema
        schema = {
            "title": "ProjectMetadata",
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "deadline": {"type": "string", "format": "date-time"}
            }
        }
        
        # Register the schema
        result = register_schema(
            db_path="/fake/path",
            node_type="project",
            schema_version=1,
            json_schema=schema
        )
        
        # Check the result
        assert result is True
        
        # Verify Dolt methods were called
        mock_dolt.sql.assert_called_once()
        mock_dolt.add.assert_called_once_with("node_schemas")
        mock_dolt.commit.assert_called_once()
        
        # Check the SQL query contains INSERT
        call_args, call_kwargs = mock_dolt.sql.call_args
        assert 'query' in call_kwargs
        assert 'INSERT INTO node_schemas' in call_kwargs['query']
        assert 'args' in call_kwargs
        assert len(call_kwargs['args']) == 4
        assert call_kwargs['args'][0] == "project"
        assert call_kwargs['args'][1] == 1
        assert isinstance(call_kwargs['args'][2], str)  # JSON string
        # args[3] should be a datetime string
    
    def test_register_schema_error(self, mock_dolt):
        """Test error handling when registering a schema."""
        # Make the sql method raise an exception
        mock_dolt.sql.side_effect = Exception("Database error")
        
        # Try to register the schema
        result = register_schema(
            db_path="/fake/path",
            node_type="project",
            schema_version=1,
            json_schema={}
        )
        
        # Check the result
        assert result is False
    
    def test_register_all_metadata_schemas(self, mock_dolt):
        """Test registering all metadata schemas."""
        # Patch get_all_metadata_models to return our test models
        with patch('experiments.src.memory_system.dolt_schema_manager.get_all_metadata_models') as mock_get_models:
            # Create a mapping similar to what get_all_metadata_models would return
            metadata_map = {
                "project": ProjectMetadata,
                "task": TaskMetadata,
                "doc": DocMetadata,
                "knowledge": KnowledgeMetadata
            }
            mock_get_models.return_value = metadata_map
            
            # Call the function
            results = register_all_metadata_schemas(db_path="/fake/path")
            
            # Check the results
            assert isinstance(results, dict)
            assert "project" in results
            assert "task" in results
            assert "doc" in results
            assert "knowledge" in results
            
            # Verify Dolt methods were called for each schema
            assert mock_dolt.sql.call_count == len(metadata_map)
            assert mock_dolt.add.call_count == len(metadata_map)
            assert mock_dolt.commit.call_count == len(metadata_map)
    
    def test_get_schema(self, mock_dolt):
        """Test retrieving a schema definition."""
        # Prepare a mock result
        mock_dolt.sql.return_value = {
            'rows': [
                {
                    'json_schema': json.dumps({"title": "ProjectMetadata"}),
                    'schema_version': 1,
                    'created_at': datetime.now().isoformat()
                }
            ]
        }
        
        # Get the schema
        schema = get_schema(
            db_path="/fake/path",
            node_type="project"
        )
        
        # Check the schema
        assert schema is not None
        assert schema['title'] == "ProjectMetadata"
        assert 'x_schema_version' in schema
        assert 'x_created_at' in schema
        
        # Verify Dolt sql method was called
        mock_dolt.sql.assert_called_once()
        
        # Check the SQL query contains SELECT
        call_args, call_kwargs = mock_dolt.sql.call_args
        assert 'query' in call_kwargs
        assert 'SELECT' in call_kwargs['query']
        assert 'args' in call_kwargs
        assert call_kwargs['args'] == ["project"]
    
    def test_get_schema_specific_version(self, mock_dolt):
        """Test retrieving a specific schema version."""
        # Prepare a mock result
        mock_dolt.sql.return_value = {
            'rows': [
                {
                    'json_schema': json.dumps({"title": "ProjectMetadata", "version": 2}),
                    'schema_version': 2,
                    'created_at': datetime.now().isoformat()
                }
            ]
        }
        
        # Get the schema with specific version
        schema = get_schema(
            db_path="/fake/path",
            node_type="project",
            schema_version=2
        )
        
        # Check the schema
        assert schema is not None
        assert schema['title'] == "ProjectMetadata"
        assert schema['version'] == 2
        
        # Verify Dolt sql method was called with the right args
        call_args, call_kwargs = mock_dolt.sql.call_args
        assert 'args' in call_kwargs
        assert call_kwargs['args'] == ["project", 2]
    
    def test_get_schema_not_found(self, mock_dolt):
        """Test retrieving a schema that doesn't exist."""
        # Prepare an empty result
        mock_dolt.sql.return_value = {'rows': []}
        
        # Try to get a non-existent schema
        schema = get_schema(
            db_path="/fake/path",
            node_type="nonexistent"
        )
        
        # Check the result
        assert schema is None
    
    def test_list_available_schemas(self, mock_dolt):
        """Test listing available schemas."""
        # Prepare a mock result
        mock_dolt.sql.return_value = {
            'rows': [
                {
                    'node_type': 'project',
                    'schema_version': 2,
                    'created_at': datetime.now().isoformat()
                },
                {
                    'node_type': 'project',
                    'schema_version': 1,
                    'created_at': datetime.now().isoformat()
                },
                {
                    'node_type': 'task',
                    'schema_version': 1,
                    'created_at': datetime.now().isoformat()
                }
            ]
        }
        
        # List the schemas
        schemas = list_available_schemas(db_path="/fake/path")
        
        # Check the result
        assert len(schemas) == 3
        assert schemas[0]['node_type'] == 'project'
        assert schemas[0]['schema_version'] == 2
        assert schemas[2]['node_type'] == 'task'
        
        # Verify Dolt sql method was called
        mock_dolt.sql.assert_called_once()
        
        # Check the SQL query
        call_args, call_kwargs = mock_dolt.sql.call_args
        assert 'query' in call_kwargs
        assert 'SELECT node_type, schema_version, created_at' in call_kwargs['query']

    @pytest.mark.parametrize("model_cls", [
        ProjectMetadata,
        TaskMetadata,
        DocMetadata,
        KnowledgeMetadata
    ])
    def test_pydantic_model_json_schema(self, model_cls):
        """Test that each Pydantic model can generate valid JSON schema."""
        # Get the JSON schema from the model
        json_schema = model_cls.model_json_schema()
        
        # Check basic structure
        assert isinstance(json_schema, dict)
        assert 'title' in json_schema
        assert json_schema['title'] == model_cls.__name__
        assert 'type' in json_schema
        assert json_schema['type'] == 'object'
        assert 'properties' in json_schema
        
        # Make sure we can serialize it to JSON
        json_str = json.dumps(json_schema)
        assert isinstance(json_str, str)
        
        # Verify we can parse it back to a dict
        parsed = json.loads(json_str)
        assert parsed == json_schema
        
    def test_validate_metadata_valid(self):
        """Test validation of valid metadata."""
        # Patch get_metadata_model to return ProjectMetadata
        with patch('experiments.src.memory_system.schemas.registry.get_metadata_model') as mock_get_model:
            mock_get_model.return_value = ProjectMetadata
            
            # Valid project metadata
            valid_metadata = {
                "name": "Test Project",
                "description": "A test project",
                "status": "planning",
                "completed": False
            }
            
            # Validate metadata
            result = validate_metadata("project", valid_metadata)
            
            # Check result
            assert result is True
            mock_get_model.assert_called_once_with("project")
    
    def test_validate_metadata_invalid(self):
        """Test validation of invalid metadata."""
        # Patch get_metadata_model to return ProjectMetadata
        with patch('experiments.src.memory_system.schemas.registry.get_metadata_model') as mock_get_model:
            mock_get_model.return_value = ProjectMetadata
            
            # Invalid project metadata (missing required fields)
            invalid_metadata = {
                "status": "invalid_status",  # Invalid enum value
                "completed": "not_a_boolean"  # Wrong type
            }
            
            # Validate metadata
            result = validate_metadata("project", invalid_metadata)
            
            # Check result
            assert result is False
            mock_get_model.assert_called_once_with("project")
    
    def test_validate_metadata_missing_model(self):
        """Test validation when no model exists for the block type."""
        # Patch get_metadata_model to return None (no model found)
        with patch('experiments.src.memory_system.schemas.registry.get_metadata_model') as mock_get_model:
            mock_get_model.return_value = None
            
            # Any metadata
            metadata = {"some_field": "some_value"}
            
            # Validate metadata with non-existent block type
            result = validate_metadata("nonexistent", metadata)
            
            # Check result
            assert result is False
            mock_get_model.assert_called_once_with("nonexistent")

    def test_get_available_node_types(self):
        """
        Test that get_available_node_types returns all expected node types.
        This is a fully integrated test with no mocking that hardcodes the expected types.
        If a new node type is added, this test should be updated.
        """
        
        # Get the available node types
        node_types = get_available_node_types()
        
        # Define the expected node types - UPDATE THIS LIST when adding new node types
        expected_types = ["project", "task", "doc", "knowledge"]
        
        # Verify all expected types are present
        assert set(node_types) == set(expected_types), \
            f"Expected node types {expected_types}, but got {node_types}. If you added a new node type, update the expected_types list in this test."
        
        # Also verify the count to ensure we catch additions and removals
        assert len(node_types) == len(expected_types), \
            f"Expected {len(expected_types)} node types, but got {len(node_types)}. If you added or removed a node type, update the expected_types list in this test." 