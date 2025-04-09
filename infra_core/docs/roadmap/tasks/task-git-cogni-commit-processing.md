# Task: Implement Commit Processing for GitCogni
:type: Task
:status: in_progress
:project: [[project-git-cogni-agent]]
:owner:
- ## Description
  Adapt existing commit diff script for use with GitCogni to extract and process commit information.

- ## Action Items
- [x] Identify/initial processing of PR using Pygithub 
- [ ] Adapt `scripts/generate_commit_diffs_cognigraph_main.sh` for PR review
- [ ] Create Python wrapper to call the script within Prefect workflow
- [ ] Implement parameter injection for base and head branches
- [ ] Create function to read and parse generated diff files
- ## Notes
  This will build upon the existing commit diff generation script (`scripts/generate_commit_diffs_cognigraph_main.sh`) which already handles generating diff files. We'll adapt it to work with the PR branches and integrate with Prefect.
- ## Estimated Effort
- Hours: 2
- ## Dependencies
- Access to Git repository