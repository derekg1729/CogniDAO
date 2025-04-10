# git-cogni-agent
:type: Project
:status: completed-v1
:project: [[Epic_Presence_and_Control_Loops]]

## Description
Launch a single Git-Cogni agent, guided by spirit context, that reviews the diff and outputs a markdown review.

What is git-Cogni? The spirit of the guardian of Cogni's git repo. Highly protective, highly pedantic.

V1 has been successfully implemented and tested, with the agent able to review PRs including its own implementation (PR #4). It provides detailed commit-by-commit analysis and a final verdict with actionable recommendations.

## Implementation Tasks
- [x] [[task-git-cogni-setup-prefect]] - Prefect workflow orchestration
- [ ] [[task-git-cogni-langchain-integration]] - LLM integration using LangChain (deprioritized)
- [x] [[task-git-cogni-commit-processing]] - Process commit diffs for review
- [x] [[task-git-cogni-review-formatting]] - Format review results as markdown
- [x] [[task-git-cogni-spirit-context]] - Implement spirit guide context
- [x] [[task-git-cogni-openai-integration]] - Direct OpenAI integration for LLM review

## MVP Flow (completed)
1. [x] Manually triggered prefect flow 
2. [x] Identify PR to review (branch/commit range)
3. [x] Load GitCogni spirit context
4. [x] Process each commit in PR:
   - [x] Extract commit diff and metadata
   - [x] Send to LLM for review (direct OpenAI)
   - [x] Store analysis in memory
5. [x] Generate final summary with all analyses
6. [x] Output markdown review with decision

## Future Enhancements
- [ ] Improved test coverage
- [ ] Enhanced CLI tool
- [ ] Support for private repositories
- [ ] More efficient handling of very large PRs
- [ ] LangChain integration (if needed)
