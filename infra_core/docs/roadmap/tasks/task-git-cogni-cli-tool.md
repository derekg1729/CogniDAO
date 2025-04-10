# Task: Refactor GitCogni CLI and Flow for Consistency
:type: Task
:status: in_progress
:project: [[project-git-cogni-agent]]
:owner:

## Description
Refactor the GitCogni CLI tool and Prefect Flow to share implementation, minimizing code duplication and ensuring consistent behavior.

## Action Items
- [ ] Move logging setup from CLI to GitCogniAgent class
- [ ] Create standardized verdict extraction helper in GitCogniAgent
- [ ] Move monitoring/instrumentation into core agent class
- [ ] Refactor CLI as thin wrapper around agent methods
- [ ] Ensure Flow uses the same agent methods as CLI
- [ ] Add tests for shared functionality
- [ ] Document unified approach for future enhancements

## Notes
The current implementation has significant duplication between the CLI tool and the Prefect Flow, creating maintenance challenges and potential for inconsistent behavior. Key issues identified:

1. Duplicate logging setup and configuration
2. Separate verdict extraction and formatting logic
3. CLI-specific monitoring that should be available to all users
4. Different error handling approaches

The refactoring should enable a unified codebase where 99% of the logic is in the GitCogniAgent class, with both CLI and Flow serving as thin wrappers. This ensures all features, monitoring, and error handling are consistently available regardless of how GitCogni is invoked.

## Estimated Effort
- Hours: 3-4 (estimated)

## Dependencies
- Completed GitCogniAgent implementation (✓)
- Completed Prefect flow (✓) 