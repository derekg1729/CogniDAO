# CogniAgent Tests

This directory contains test suites for the CogniAgent classes in the CogniDAO system.

## Test Structure

The tests are organized as follows:

- `test_base_agent.py`: Tests for the abstract base `CogniAgent` class
- `test_git_cogni_agent.py`: Tests for the `GitCogniAgent` implementation

## Running Tests

You can run all agent tests from the project root with:

```bash
./test.py tests/agents/
```

To run a specific test file:

```bash
./test.py tests/agents/test_base_agent.py
```

## Test Approach

The tests use Python's `unittest` framework with mocking (`unittest.mock`) to isolate components and verify behaviors. Some key techniques used:

1. **Abstract Class Testing**: We create a concrete test implementation of the abstract `CogniAgent` to test its base functionality.

2. **Dependency Mocking**: External dependencies like the GitHub API, filesystem operations, and OpenAI clients are all mocked.

3. **Time-dependent Testing**: For methods that use `datetime.utcnow()`, we use class-level patching to provide deterministic timestamps.

4. **Error Path Testing**: Each agent has tests for error handling and edge cases.

## Adding New Agent Tests

When creating a new agent, follow this pattern:

1. Create a new test file named `test_your_agent_name.py`
2. Import and subclass `unittest.TestCase`
3. Mock any external dependencies
4. Test initialization, success paths, and error handling
5. Use the existing test files as templates

## Common Testing Patterns

### Mocking Datetime

For consistent datetime testing:

```python
# Create a mock datetime class
class MockDateTime:
    @classmethod
    def utcnow(cls):
        return datetime(2023, 1, 1, 12, 0, 0)

# Patch at the module level where datetime is imported
@patch('your_module.datetime', MockDateTime)
def test_your_time_dependent_method(self):
    # Test code that uses datetime.utcnow()
```

### Mocking File Operations

```python
# Mock Path objects
mock_path = MagicMock(spec=Path)
mock_path.exists.return_value = True
mock_path.read_text.return_value = "Test content"

# Mock write operations
@patch('pathlib.Path.write_text')
def test_file_writing(self, mock_write_text):
    # Test code that writes to files
``` 