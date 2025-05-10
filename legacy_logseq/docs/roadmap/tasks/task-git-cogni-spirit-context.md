# Task: Implement Spirit Guide Context for GitCogni
:type: Task
:status: completed
:project: [[project-git-cogni-agent]]
:owner:

## Description
Create the git-cogni spirit guide file and use the existing spirit context functionality for GitCogni agent.

## Action Items
- [x] Create `git-cogni.md` spirit guide file with review personality and guidelines
- [x] Use existing functions from `legacy_logseq/cogni_spirit/context.py` 
- [x] Add git-cogni to guides directory for auto-loading
- [x] Integrate with Prefect task using existing `get_guide_for_task` function

## Notes
The implementation leverages the simplified spirit context infrastructure in the codebase. We've integrated the git-cogni spirit guide with the Prefect workflow and added proper metadata logging. The task has been fully completed.

## Estimated Effort
- Hours: 1 (actual)

## Dependencies
- None