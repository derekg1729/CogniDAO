# Task: Implement Test Mode for GitCogni
:type: Task
:status: completed
:project: [[project-git-cogni-agent]]
:owner:

## Description
Add a test mode to GitCogni CLI that cleans up generated markdown files after successful execution, useful for CI/CD environments and testing.

## Action Items
- [x] Add `--test` flag to CLI interface
- [x] Modify GitCogniAgent to track created files
- [x] Implement cleanup logic to remove files after successful review
- [x] Add warning message before cleanup
- [x] Update CLI tests to verify test mode functionality
- [x] Document test mode usage in help message

## Notes
During testing, GitCogni creates numerous markdown files in the reviews and errors directories. While these are valuable for debugging and record-keeping in production, they can clutter the repository during development and testing.

The test mode will provide a clean way to run GitCogni without leaving behind artifact files, making it suitable for CI/CD pipelines and local development testing. Files will only be cleaned up after successful execution to ensure error logs are preserved when needed.

## Estimated Effort
- Hours: 2 (estimated)

## Dependencies
- Completed GitCogniAgent implementation (✓)
- Refactored CLI implementation (✓) 