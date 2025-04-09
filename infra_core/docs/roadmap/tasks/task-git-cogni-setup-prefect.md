# Task: Setup Prefect Orchestration for GitCogni
:type: Task
:status: needs_review
:project: [[project-git-cogni-agent]]
:owner:
- ## Description
  Set up Prefect workflow orchestration for the GitCogni agent using established Cogni patterns.
- ## Action Items
- [x] Create GitCogni Prefect flow leveraging existing task structure
- [x] Use the existing Prefect deployment practices (local storage)
- [ ] Set up appropriate flow concurrency controls and retries
- [x] Implement PR parameter handling for branch selection
- ## Notes
  This will follow the established Prefect patterns already in use for other Cogni workflows. The implementation will focus on integrating with existing spirit context loading and deployment practices.
- ## Estimated Effort
- Hours: 2
- ## Dependencies
- Python environment with Prefect installed