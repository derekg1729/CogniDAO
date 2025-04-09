# Task: Implement Commit Processing for GitCogni
:type: Task
:status: in_progress
:project: [[project-git-cogni-agent]]
:owner:
- ## Description
  Adapt existing commit diff script for use with GitCogni to extract and process commit information.

- ## Action Items
- [x] Identify/initial processing of PR using Pygithub 
- [x] Create Python implementation for PR commit retrieval
- [x] Implement parameter injection for base and head branches
- [x] Create function to retrieve commit data
- ## Notes
  This now uses PyGithub API directly instead of the shell script, making it more integrated and portable. The implementation retrieves commit data including SHA, message, author, date, and file changes.
- ## Estimated Effort
- Hours: 2
- ## Dependencies
- Access to Git repository