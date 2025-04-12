# Task: Implement LogSeq Integration for Broadcast
:type: Task
:status: not-started
:project: [[project-broadcast-cogni]]
:owner:

## Description
Implement LogSeq integration components for BroadcastCogni to enable human approval workflow and track broadcast status.

## Action Items
- [ ] Implement property-based query for finding approved thoughts
- [ ] Create utility to parse LogSeq properties
- [ ] Implement function to update LogSeq properties after broadcasting
- [ ] Test LogSeq property updates for race conditions
- [ ] Ensure dashboard queries work properly

## Implementation Details
- Query should find pages with `broadcast-approved: true`
- Should handle various property formats gracefully
- Must extract content from `broadcast-content` property
- Must extract target channels from `broadcast-channels` array
- Updates should preserve other page properties

## Success Criteria
- Successfully finds approved thoughts in LogSeq
- Correctly extracts broadcast content and target channels
- Updates page properties after broadcasting without data loss
- Dashboard queries show thoughts in appropriate categories
- Handles malformed properties gracefully

## Estimated Effort
- Hours: 4-6

## Dependencies
- Task-broadcast-git-branch 