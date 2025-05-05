# Task: Setup Git Branch for Broadcast Approvals
:type: Task
:status: not-started
:project: [[project-broadcast-cogni]]
:owner:

## Description
Create and configure a dedicated git branch for BroadcastCogni that will track broadcast approvals, queue state, and posting history.

## Action Items
- [ ] Create a new git branch named `broadcast` from main
- [ ] Set up directory structure for queue and logs
- [ ] Create initial queue.json from template
- [ ] Document branch usage in README
- [ ] Implement git utility functions to ensure operations on correct branch

## Implementation Details
- Branch should be created from the latest main
- Directory structure should include:
  - `presence/broadcast/queue.json`
  - `presence/broadcast/logs/`
- Initial queue.json should use the template with empty queue and history

## Success Criteria
- Branch exists and can be checked out
- Directory structure is properly set up
- Basic git operations (checkout, commit) are working
- Utility functions correctly detect and switch to broadcast branch

## Estimated Effort
- Hours: 1-2

## Dependencies
- None 