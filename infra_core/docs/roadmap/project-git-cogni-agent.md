# git-cogni-agent
:type: Project
:status: in-progress
:project: [[Epic_Presence_and_Control_Loops]]

## Description
Launch a single Git-Cogni agent, guided by spirit context, that reviews the diff and outputs a markdown review.

What is git-Cogni? The spirit of the guardian of Cogni's git repo. Highly protective, highly pedantic.

## Implementation Tasks
- [x] [[task-git-cogni-setup-prefect]] - Prefect workflow orchestration
- [ ] [[task-git-cogni-langchain-integration]] - LLM integration using LangChain
- [x] [[task-git-cogni-commit-processing]] - Process commit diffs for review
- [ ] [[task-git-cogni-review-formatting]] - Format review results as markdown
- [x] [[task-git-cogni-spirit-context]] - Implement spirit guide context

## MVP Flow
1. [x] Manually triggered prefect flow 
2. [x] Identify PR to review (branch/commit range)
3. [x] Load GitCogni spirit context
4. [x] Process each commit in PR:
   - [x] Extract commit diff and metadata
   - [ ] Send to LLM for review
   - [ ] Store analysis in memory
5. [ ] Generate final summary with all analyses
6. [ ] Output markdown review with decision
