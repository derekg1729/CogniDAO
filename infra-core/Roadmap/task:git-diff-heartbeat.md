# Task:git-diff-heartbeat
:status: in_progress
:project: infra-core

## Description
Detects new changes in the Git repo on each heartbeat and stores the `git diff` to a file for agent consumption.

## Steps
- [ ] Detect repo changes using `git diff`
- [ ] Hash and compare with last known state
- [ ] Save to `pending_review.diff` if changed
- [ ] Trigger review pipeline
