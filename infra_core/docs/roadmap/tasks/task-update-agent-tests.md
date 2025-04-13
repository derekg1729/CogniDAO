# Task:[Update Agent Tests for Memory Integration]
:type: Task
:status: in-progress
:project: [Agent Memory Integration]
- ## Current Status
  With the implementation of the new Agent base class and migration of GitCogni and BroadcastCogni to use it, we need to update all tests to work with the new architecture. This includes creating proper mocking patterns for the MemoryClient in agent tests. GitCogni tests have been successfully updated and are now passing.
- ## Description
  Update all agent tests to work with the new Agent base class architecture. Create standardized mocking patterns for MemoryClient to ensure consistent and reliable testing. This will maintain test coverage and ensure the new implementation behaves correctly.
- ## Action Items
- [x] Create standardized mocking patterns for MemoryClient
	- [x] Create a MockMemoryClient class for testing
	- [x] Define standard responses for common method calls
	- [x] Document usage patterns for agent tests
- [x] Update GitCogni tests
	- [x] Replace context.py mocks with MemoryClient mocks
	- [x] Update test cases to work with the new Agent base class
	- [x] Add tests for new query_relevant_context functionality

- [x] Update integration tests
	- [x] Remove references to context.py from test files
	- [x] Ensure end-to-end tests work with the new architecture
	- [x] Update test fixtures and mocks as needed
- ## Deliverables
  1. MockMemoryClient implementation for testing
  2. Updated GitCogni tests
  3. Updated BroadcastCogni tests
  4. Updated integration tests
  5. Documentation for testing with the new architecture
- ## Test Criteria
- [x] All tests pass
- [x] Test coverage maintained or improved
- [x] Mocking patterns are consistent across all tests
- [x] New functionality is adequately tested
- ## Implementation Notes
- ### MockMemoryClient Example:
  ```python
  # test_utils.py
  from unittest.mock import MagicMock
  from typing import Dict, List, Optional, Any, Union
  
  class MockMemoryClient:
    """Mock implementation of CogniMemoryClient for testing."""
    
    def __init__(self, mock_pages: Optional[Dict[str, str]] = None, mock_queries: Optional[Dict[str, List[Dict]]] = None):
        """
        Initialize with optional mock data.
        
        Args:
            mock_pages: Dictionary mapping file paths to content
            mock_queries: Dictionary mapping query strings to lists of result blocks
        """
        self.mock_pages = mock_pages or {
            "CHARTER.md": "# Mock Charter\nThis is a mock charter for testing.",
            "MANIFESTO.md": "# Mock Manifesto\nThis is a mock manifesto for testing.",
            "infra_core/cogni_spirit/spirits/cogni-core-spirit.md": "# Mock Core Spirit\nThis is a mock core spirit guide."
        }
        
        self.mock_queries = mock_queries or {}
        
        # Track calls for assertions
        self.get_page_calls = []
        self.query_calls = []
    
    def get_page(self, filepath: str) -> str:
        """Mock implementation of get_page."""
        self.get_page_calls.append(filepath)
        
        if filepath in self.mock_pages:
            return self.mock_pages[filepath]
        
        # For paths not explicitly mocked, generate content
        return f"Mock content for {filepath}"
    
    def query(self, query_text: str, n_results: int = 5, filter_tags: Optional[List[str]] = None, **kwargs) -> Any:
        """Mock implementation of query."""
        self.query_calls.append({"query": query_text, "n_results": n_results, "filter_tags": filter_tags})
        
        # Use predefined results if available
        if query_text in self.mock_queries:
            result_blocks = self.mock_queries[query_text][:n_results]
        else:
            # Generate mock results
            result_blocks = [
                {"id": f"block-{i}", "text": f"Mock result {i} for query: {query_text}", "source_file": "mock.md", "tags": ["#mock"]}
                for i in range(min(3, n_results))
            ]
        
        # Create a result object that mimics QueryResult
        result = MagicMock()
        result.blocks = result_blocks
        result.query_text = query_text
        result.total_results = len(result_blocks)
        
        return result
  ```
- ### Example Test Case:
  ```python
  def test_git_cogni_review_with_mock_memory():
    """Test GitCogni review with MockMemoryClient."""
    # Create mock memory client with test data
    mock_memory = MockMemoryClient(
        mock_pages={
            "CHARTER.md": "# Test Charter",
            "infra_core/cogni_spirit/spirits/cogni-code-review.md": "# Code Review Guidelines\nTest guidelines."
        },
        mock_queries={
            "test commit message": [
                {"id": "block-1", "text": "Relevant context for test commit", "source_file": "test.md", "tags": []}
            ]
        }
    )
    
    # Create GitCogni with mocked memory
    git_cogni = GitCogni()
    git_cogni.memory = mock_memory
    
    # Create test commit
    test_commit = {"message": "test commit message", "sha": "abc123"}
    
    # Call the method under test
    result = git_cogni.review_commit(test_commit)
    
    # Assertions
    assert "test.md" in str(result)  # Relevant context was included
    assert mock_memory.get_page_calls  # get_page was called
    assert mock_memory.query_calls  # query was called
    assert any("test commit message" in call["query"] for call in mock_memory.query_calls)  # Query used commit message
  ```
- ## Dependencies
- Completed [[task-implement-agent-base-memory]]
- Completed [[task-migrate-git-cogni]]
- Completed [[task-migrate-broadcast-cogni]]
- Understanding of existing testing patterns