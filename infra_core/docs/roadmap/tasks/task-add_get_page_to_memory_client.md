# Task:[Add get_page() to CogniMemoryClient]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Add a `get_page()` method to CogniMemoryClient that loads the full content of any markdown file. This enables direct access to raw markdown content without the block-based extraction, providing a complete view of a page for scenarios requiring the entire document.

## Action Items
- [ ] Add a `get_page(filepath)` method to CogniMemoryClient
- [ ] Implement proper file path validation and error handling
- [ ] Support both absolute and relative paths
- [ ] Add options for metadata extraction (frontmatter)
- [ ] Add type hints and comprehensive docstrings
- [ ] Write unit tests in test_memory_client.py

## Deliverables
1. Implementation of `get_page()` in memory_client.py:
   ```python
   def get_page(
       self, 
       filepath: str,
       extract_frontmatter: bool = False
   ) -> Union[str, Tuple[str, Dict]]:
       """
       Load the full content of a markdown file.
       
       Args:
           filepath: Path to the markdown file (absolute or relative path)
           extract_frontmatter: Whether to extract frontmatter metadata (default: False)
           
       Returns:
           If extract_frontmatter is False:
               Raw markdown content as a string
           If extract_frontmatter is True:
               Tuple of (content, frontmatter_dict)
               
       Raises:
           FileNotFoundError: If the file does not exist
           PermissionError: If the file cannot be read due to permissions
       """
   ```

2. Unit tests in test_memory_client.py

## Test Criteria
- [ ] Test loading a markdown file with content:
```python
def test_get_page():
    # Setup test file
    test_dir = "./test_markdown"
    os.makedirs(test_dir, exist_ok=True)
    
    test_content = "# Test Page\n\nThis is a test page with markdown content.\n\n- Item 1\n- Item 2"
    test_file = f"{test_dir}/test_page.md"
    
    with open(test_file, "w") as f:
        f.write(test_content)
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test getting page content
    content = client.get_page(test_file)
    assert content == test_content
    
    # Test with relative path
    relative_path = os.path.relpath(test_file)
    content = client.get_page(relative_path)
    assert content == test_content
    
    # Clean up
    shutil.rmtree(test_dir)
```

- [ ] Test loading a markdown file with frontmatter:
```python
def test_get_page_with_frontmatter():
    # Setup test file with frontmatter
    test_dir = "./test_markdown"
    os.makedirs(test_dir, exist_ok=True)
    
    test_content = """---
title: Test Document
tags: [test, markdown]
date: 2023-07-01
---

# Test Page

This is a test page with frontmatter."""
    
    test_file = f"{test_dir}/frontmatter_test.md"
    
    with open(test_file, "w") as f:
        f.write(test_content)
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test getting page with frontmatter extraction
    content, frontmatter = client.get_page(test_file, extract_frontmatter=True)
    
    assert "# Test Page" in content
    assert frontmatter["title"] == "Test Document"
    assert "test" in frontmatter["tags"]
    assert frontmatter["date"] == "2023-07-01"
    
    # Clean up
    shutil.rmtree(test_dir)
```

- [ ] Test error handling for non-existent files:
```python
def test_get_page_file_not_found():
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test with non-existent file
    with pytest.raises(FileNotFoundError):
        client.get_page("./nonexistent_file.md")
```

## Notes
- The method should support both absolute and relative file paths
- Implement clean error handling for common file access issues
- Consider adding an option to extract frontmatter metadata
- Focus on simplicity and reliability for this core file access function

## Dependencies
- Python frontmatter library (if supporting frontmatter extraction)
- Standard Python file I/O 