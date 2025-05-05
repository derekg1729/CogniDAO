# git-diff-heartbeat
:type: Project
:status: in_progress
:epic: [[Epic_Presence_and_Control_Loops]]
:owner: 

## Description
Detects new changes in the Git repo on each heartbeat and stores the `git diff` to a file for agent consumption.

## Steps
- [ ] Detect repo changes using `git diff`
- [ ] Hash and compare with last known state
- [ ] Save to `pending_review.diff` if changed
- [ ] Trigger review pipeline
