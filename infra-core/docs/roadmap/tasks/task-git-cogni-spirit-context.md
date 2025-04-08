# Task: Implement Spirit Guide Context for GitCogni
:type: Task
:status: todo
:project: [[project-git-cogni-agent]]
:owner:

## Description
Create the git-cogni spirit guide file and use the existing spirit context functionality for GitCogni agent.

## Action Items
- [ ] Create `git-cogni.md` spirit guide file with review personality and guidelines
- [ ] Use existing `SpiritContext` class from `infra-core/cogni_spirit/context.py`
- [ ] Add git-cogni to guides directory for auto-loading
- [ ] Integrate with Prefect task using existing `get_guide_for_task` function

## Notes
The implementation will leverage the existing spirit context infrastructure that's already in place in the codebase. The `SpiritContext` class and Prefect tasks for loading contexts are already available.

## Estimated Effort
- Hours: 1

## Dependencies
- None