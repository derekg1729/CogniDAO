# Task:[Add write_page() to CogniMemoryClient]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Add a `write_page()` method to CogniMemoryClient that enables writing or appending agent output to markdown files. This provides a way for agents to create, update, or append to Logseq pages, creating a visible record of agent activity that's accessible to humans through their normal Logseq interface.

## Action Items
- [ ] Add a `write_page(filepath, content, append=False)` method to CogniMemoryClient
- [ ] Implement proper file path validation and directory creation
- [ ] Support both append and overwrite modes
- [ ] Add options for frontmatter addition to new pages
- [ ] Implement proper error handling for file operations
- [ ] Add type hints and comprehensive docstrings
- [ ] Write unit tests in test_memory_client.py

## Deliverables
1. Implementation of `write_page()` in memory_client.py:
   ```python
   def write_page(
       self, 
       filepath: str, 
       content: str, 
       append: bool = False,
       frontmatter: Optional[Dict[str, Any]] = None
   ) -> str:
       """
       Write or append content to a markdown file.
       
       Args:
           filepath: Path to the markdown file (absolute or relative path)
           content: Content to write to the file
           append: Whether to append to the file (default: False)
           frontmatter: Optional frontmatter to add to new pages
           
       Returns:
           Path to the written file
           
       Raises:
           PermissionError: If the file cannot be written due to permissions
           OSError: For other file system errors
       """
   ```

2. Unit tests in test_memory_client.py

## Test Criteria
- [ ] Test writing a new markdown file:
```python
def test_write_page_new_file():
    # Setup test directory
    test_dir = "./test_markdown"
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = f"{test_dir}/new_page.md"
    test_content = "# New Page\n\nThis is a new page created by the memory client."
    
    # Remove file if it exists (for test cleanliness)
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test writing new file
    filepath = client.write_page(test_file, test_content)
    
    # Verify file was created with correct content
    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        content = f.read()
    assert content == test_content
    
    # Clean up
    shutil.rmtree(test_dir)
```

- [ ] Test appending to an existing file:
```python
def test_write_page_append():
    # Setup test directory and file
    test_dir = "./test_markdown"
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = f"{test_dir}/append_test.md"
    initial_content = "# Existing Page\n\nThis is an existing page.\n"
    
    with open(test_file, "w") as f:
        f.write(initial_content)
    
    append_content = "\n## New Section\n\nThis content was appended."
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test appending to file
    filepath = client.write_page(test_file, append_content, append=True)
    
    # Verify content was appended
    with open(filepath, "r") as f:
        content = f.read()
    assert content == initial_content + append_content
    
    # Clean up
    shutil.rmtree(test_dir)
```

- [ ] Test overwriting an existing file:
```python
def test_write_page_overwrite():
    # Setup test directory and file
    test_dir = "./test_markdown"
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = f"{test_dir}/overwrite_test.md"
    initial_content = "# Old Content\n\nThis content should be replaced.\n"
    
    with open(test_file, "w") as f:
        f.write(initial_content)
    
    new_content = "# New Content\n\nThis content replaces the old content."
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test overwriting file
    filepath = client.write_page(test_file, new_content, append=False)
    
    # Verify content was overwritten
    with open(filepath, "r") as f:
        content = f.read()
    assert content == new_content
    
    # Clean up
    shutil.rmtree(test_dir)
```

- [ ] Test adding frontmatter to a new file:
```python
def test_write_page_with_frontmatter():
    # Setup test directory
    test_dir = "./test_markdown"
    os.makedirs(test_dir, exist_ok=True)
    
    test_file = f"{test_dir}/frontmatter_test.md"
    test_content = "# Page With Frontmatter\n\nThis page has frontmatter."
    
    # Remove file if it exists
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # Initialize client
    client = CogniMemoryClient(
        chroma_path="./test_chroma",
        archive_path="./test_archive"
    )
    
    # Test writing with frontmatter
    frontmatter_data = {
        "title": "Test Page",
        "tags": ["test", "frontmatter"],
        "date": "2023-07-01"
    }
    
    filepath = client.write_page(
        test_file, 
        test_content, 
        frontmatter=frontmatter_data
    )
    
    # Verify file was created with frontmatter
    with open(filepath, "r") as f:
        content = f.read()
    
    assert "---" in content
    assert "title: Test Page" in content
    assert "tags:" in content
    assert "# Page With Frontmatter" in content
    
    # Parse frontmatter to verify
    parsed = frontmatter.parse(content)
    assert parsed["frontmatter"]["title"] == "Test Page"
    assert "test" in parsed["frontmatter"]["tags"]
    
    # Clean up
    shutil.rmtree(test_dir)
```

## Notes
- The method should create intermediate directories if they don't exist
- Support both absolute and relative paths
- Add proper error handling for file operations
- Consider frontmatter support for new pages
- Append mode should be careful not to duplicate content
- Focus on reliable file operations with clear feedback

## Dependencies
- Python frontmatter library (for frontmatter support)
- Standard Python file I/O
- Path handling utilities 