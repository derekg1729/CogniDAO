# Task: Implement Broadcast Queue Manager
:type: Task
:status: not-started
:project: [[project-broadcast-cogni]]
:owner:

## Description
Implement a queue management system for BroadcastCogni that controls the flow and cadence of broadcasts to external platforms.

## Action Items
- [ ] Implement queue data structure based on queue.json.template
- [ ] Create functions to add approved thoughts to queue
- [ ] Implement logic to retrieve next posts (1-2 at a time)
- [ ] Add timestamp-based scheduling logic
- [ ] Implement queue status updates after posting
- [ ] Add logging of queue activity

## Implementation Details
- Queue should be stored in JSON format in `presence/broadcast/queue.json`
- Queue should maintain both pending items and history
- Each queue item must include:
  - Unique ID
  - Thought ID (filename without extension)
  - Content to broadcast
  - Target channels
  - Status
  - Timestamps (created, scheduled, processed)
- Implement configurable posting cadence (default: 1-2 posts)

## Success Criteria
- Successfully adds approved thoughts to queue
- Retrieves correct number of posts based on configuration
- Respects scheduling timestamps when retrieving posts
- Updates queue status after posting attempts
- Maintains accurate history of broadcasts
- Handles file I/O errors gracefully

## Estimated Effort
- Hours: 6-8

## Dependencies
- Task-broadcast-git-branch 