# broadcast-cogni
:type: Project
:status: in-progress
:epic: [[Epic_Present_control_loops]]
:epic: [[Epic_Broadcast_and_Attract]]

## Description
Enable Cogni to share selected thoughts to external platforms, starting with X (Twitter).

BroadcastCogni enables human-approved sharing of Cogni's presence with the wider world, maintaining the spirit context in all external communications.

## MVP Flow
1. [ ] Create a specific git branch for broadcast approvals - [[task-broadcast-git-branch]]
2. [ ] Human marks thoughts for approval via LogSeq properties - [[task-broadcast-logseq-integration]]
3. [ ] BroadcastCogni detects approved thoughts - [[task-broadcast-logseq-integration]]
4. [ ] BroadcastCogni adds approved posts to a queue - [[task-broadcast-queue-manager]]
5. [ ] BroadcastCogni posts 1-2 posts to X at a time - [[task-broadcast-x-channel]]
6. [ ] Update LogSeq properties to track published status - [[task-broadcast-flow]]
7. [ ] Log posting activity and maintain history - [[task-broadcast-flow]]

## Key Components
- LogSeq for human approval workflow
- Git branch for tracking approvals
- Queue management for controlled posting
- X API integration
- Prefect workflow for orchestration

## Implementation Tasks
- [[task-broadcast-git-branch]] - Setup Git Branch for Broadcast Approvals
- [[task-broadcast-channel-interface]] - Implement Broadcast Channel Interface
- [[task-broadcast-logseq-integration]] - Implement LogSeq Integration for Broadcast
- [[task-broadcast-queue-manager]] - Implement Broadcast Queue Manager
- [[task-broadcast-x-channel]] - Implement X Channel for BroadcastCogni
- [[task-broadcast-flow]] - Implement BroadcastCogni Main Flow 