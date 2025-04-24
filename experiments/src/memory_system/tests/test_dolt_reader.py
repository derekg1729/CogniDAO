# Tests for Dolt Reader

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
import logging # Import logging for caplog tests

# Use absolute import path based on project structure and sys.path modification in dolt_reader
from experiments.src.memory_system.dolt_reader import read_memory_blocks
from experiments.src.memory_system.schemas.memory_block import MemoryBlock, BlockLink, ConfidenceScore

# Sample data conforming to the structure returned by repo.sql(..., result_format='json')
# which is typically {'rows': [ {col1: val1, ...}, ... ]}

# --- Basic Block --- 
SAMPLE_ROW_BASIC = {
    'id': 'basic-001',
    'type': 'knowledge',
    'schema_version': 1,
    'text': 'Basic block content.',
    'tags_json': None,
    'metadata_json': None,
    'links_json': None,
    'source_file': None,
    'source_uri': None,
    'confidence_json': None,
    'created_by': 'test_runner',
    'created_at': '2023-10-27T10:00:00',
    'updated_at': '2023-10-27T11:00:00'
}

# --- Block with All Fields --- 
SAMPLE_ROW_FULL = {
    'id': 'full-002',
    'type': 'task',
    'schema_version': 2,
    'text': 'Full block with all fields populated.',
    'tags_json': json.dumps(['dolt', 'test', 'full']),
    'metadata_json': json.dumps({'status': 'pending', 'priority': 3, 'assignee': 'agent_x'}),
    'links_json': json.dumps([{'to_id': 'basic-001', 'relation': 'related_to'}]),
    'source_file': 'tests/test_data.txt',
    'source_uri': 'file://tests/test_data.txt',
    'confidence_json': json.dumps({'ai': 0.95, 'human': 0.7}),
    'created_by': 'test_runner_full',
    'created_at': '2023-10-27T12:00:00',
    'updated_at': '2023-10-27T13:00:00'
}

# --- Block with Invalid JSON --- 
SAMPLE_ROW_BAD_JSON = {
    'id': 'bad-json-003',
    'type': 'doc',
    'schema_version': 1,
    'text': 'Block with bad JSON in metadata.',
    'tags_json': '["valid"]' , # Valid JSON string
    'metadata_json': '{"key": "value", invalid}', # Invalid JSON string
    'links_json': None,
    'source_file': None,
    'source_uri': None,
    'confidence_json': None,
    'created_by': 'test_runner_bad',
    'created_at': '2023-10-27T14:00:00',
    'updated_at': '2023-10-27T15:00:00'
}

# --- Block Violating Pydantic Schema --- 
SAMPLE_ROW_BAD_SCHEMA = {
    'id': 'bad-schema-004',
    'type': 'invalid_type', # Violates Literal constraint
    'schema_version': 1,
    'text': 'Block violating schema.',
    'tags_json': None,
    'metadata_json': None,
    'links_json': None,
    'source_file': None,
    'source_uri': None,
    'confidence_json': None,
    'created_by': 'test_runner_schema',
    'created_at': '2023-10-27T16:00:00',
    'updated_at': '2023-10-27T17:00:00'
}


# Patch the Dolt class within the module where it's used (dolt_reader)
DOLT_PATCH_TARGET = 'experiments.src.memory_system.dolt_reader.Dolt'

class TestDoltReader:
    
    @patch(DOLT_PATCH_TARGET)
    def test_read_basic_block(self, MockDolt):
        """Test reading a single block with basic fields."""
        # Configure mock Dolt instance and its sql method
        mock_repo = MagicMock()
        mock_repo.sql.return_value = {'rows': [SAMPLE_ROW_BASIC]}
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)
        
        assert len(blocks) == 1
        block = blocks[0]
        assert isinstance(block, MemoryBlock)
        assert block.id == 'basic-001'
        assert block.type == 'knowledge'
        assert block.text == 'Basic block content.'
        assert block.created_by == 'test_runner'
        assert block.schema_version == 1
        # Check defaults for optional/JSON fields
        assert block.tags == []
        assert block.metadata == {}
        assert block.links == []
        assert block.confidence is None
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)
        
        # Verify Dolt connection and query
        MockDolt.assert_called_once_with(db_path)
        mock_repo.sql.assert_called_once()
        # Check query contains SELECT and AS OF 'main'
        call_args, call_kwargs = mock_repo.sql.call_args
        assert 'query' in call_kwargs
        sql_query = call_kwargs['query'].upper()
        assert 'SELECT' in sql_query 
        assert "FROM MEMORY_BLOCKS" in sql_query
        assert "AS OF 'MAIN'" in sql_query # Check default branch
        assert call_kwargs['result_format'] == 'json'

    @patch(DOLT_PATCH_TARGET)
    def test_read_block_with_all_fields(self, MockDolt):
        """Test reading a block with all fields populated correctly."""
        mock_repo = MagicMock()
        mock_repo.sql.return_value = {'rows': [SAMPLE_ROW_FULL]}
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)
        
        assert len(blocks) == 1
        block = blocks[0]
        assert isinstance(block, MemoryBlock)
        assert block.id == 'full-002'
        assert block.type == 'task'
        assert block.schema_version == 2
        assert block.text == 'Full block with all fields populated.'
        assert block.tags == ['dolt', 'test', 'full']
        assert block.metadata == {'status': 'pending', 'priority': 3, 'assignee': 'agent_x'}
        assert len(block.links) == 1
        assert isinstance(block.links[0], BlockLink)
        assert block.links[0].to_id == 'basic-001'
        assert block.links[0].relation == 'related_to'
        assert block.source_file == 'tests/test_data.txt'
        assert block.source_uri == 'file://tests/test_data.txt'
        assert isinstance(block.confidence, ConfidenceScore)
        assert block.confidence.ai == 0.95
        assert block.confidence.human == 0.7
        assert block.created_by == 'test_runner_full'
        assert isinstance(block.created_at, datetime)
        assert isinstance(block.updated_at, datetime)

    @patch(DOLT_PATCH_TARGET)
    def test_read_multiple_blocks(self, MockDolt):
        """Test reading multiple blocks."""
        mock_repo = MagicMock()
        mock_repo.sql.return_value = {'rows': [SAMPLE_ROW_BASIC, SAMPLE_ROW_FULL]}
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)
        
        assert len(blocks) == 2
        assert blocks[0].id == 'basic-001'
        assert blocks[1].id == 'full-002'

    @patch(DOLT_PATCH_TARGET)
    def test_read_with_json_decode_error(self, MockDolt, caplog):
        """Test handling of JSON decode errors during parsing."""
        mock_repo = MagicMock()
        # Return one good row and one with bad metadata JSON
        mock_repo.sql.return_value = {'rows': [SAMPLE_ROW_BASIC, SAMPLE_ROW_BAD_JSON]}
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        with caplog.at_level(logging.WARNING):
            blocks = read_memory_blocks(db_path)
            
        assert len(blocks) == 2 # Should still parse both blocks
        assert blocks[0].id == 'basic-001' # First block should be fine
        assert blocks[1].id == 'bad-json-003' # Second block ID
        
        # Check that the metadata for the second block defaulted to empty dict
        assert blocks[1].metadata == {}
        assert blocks[1].tags == ["valid"] # Tags were valid JSON
        
        # Check for warning log message
        assert 'Failed to parse JSON for field \'metadata_json\'' in caplog.text
        assert "Expecting property name" in caplog.text # Check for part of the actual JSON error

    @patch(DOLT_PATCH_TARGET)
    def test_read_with_pydantic_validation_error(self, MockDolt, caplog):
        """Test handling of Pydantic validation errors."""
        mock_repo = MagicMock()
        # Return one good row and one that violates schema (invalid type)
        mock_repo.sql.return_value = {'rows': [SAMPLE_ROW_BASIC, SAMPLE_ROW_BAD_SCHEMA]}
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        with caplog.at_level(logging.ERROR):
            blocks = read_memory_blocks(db_path)
            
        # Should only return the valid block
        assert len(blocks) == 1 
        assert blocks[0].id == 'basic-001'
        
        # Check for the Pydantic validation error in logs
        assert 'Pydantic validation failed' in caplog.text
        assert 'invalid_type' in caplog.text # Mention the invalid value
        assert 'bad-schema-004' in caplog.text # Mention the block ID

    @patch(DOLT_PATCH_TARGET)
    def test_read_empty_table(self, MockDolt):
        """Test reading from an empty table."""
        mock_repo = MagicMock()
        mock_repo.sql.return_value = {'rows': []} # Simulate empty result set
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        blocks = read_memory_blocks(db_path)
        
        assert len(blocks) == 0
        assert blocks == []
        mock_repo.sql.assert_called_once()

    @patch(DOLT_PATCH_TARGET)
    def test_read_query_specific_branch(self, MockDolt):
        """Test querying a specific branch."""
        mock_repo = MagicMock()
        mock_repo.sql.return_value = {'rows': [SAMPLE_ROW_BASIC]}
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        branch_name = "dev_branch"
        blocks = read_memory_blocks(db_path, branch=branch_name)
        
        assert len(blocks) == 1
        mock_repo.sql.assert_called_once()
        call_args, call_kwargs = mock_repo.sql.call_args
        assert 'query' in call_kwargs
        # Check AS OF clause uses the specified branch
        assert f"AS OF '{branch_name}'" in call_kwargs['query']

    @patch(DOLT_PATCH_TARGET)
    def test_read_dolt_connection_error(self, MockDolt, caplog):
        """Test handling of errors during Dolt connection."""
        # Configure MockDolt constructor to raise an error
        MockDolt.side_effect = FileNotFoundError("Dolt repo not found at path")
        
        db_path = "/non/existent/path"
        with caplog.at_level(logging.ERROR):
            # Catch the specific exception we expect to be re-raised
            with pytest.raises(FileNotFoundError):
                 read_memory_blocks(db_path)
            
        # Check for error log message
        assert f"Dolt database path not found: {db_path}" in caplog.text

    @patch(DOLT_PATCH_TARGET)
    def test_read_dolt_sql_error(self, MockDolt, caplog):
        """Test handling of errors during SQL execution."""
        mock_repo = MagicMock()
        # Configure the sql method to raise an exception
        mock_repo.sql.side_effect = Exception("SQL execution failed")
        MockDolt.return_value = mock_repo
        
        db_path = "/fake/path"
        with caplog.at_level(logging.ERROR):
            blocks = read_memory_blocks(db_path)
            
        # Function should return an empty list on SQL error
        assert blocks == [] 
        
        # Check for error log message
        assert "Failed to read from Dolt DB" in caplog.text
        assert "SQL execution failed" in caplog.text