# Task: Implement Direct OpenAI Integration for GitCogni MVP
:type: Task
:status: todo
:project: [[project-git-cogni-agent]]
:owner:

## Description
Create a direct OpenAI integration for the GitCogni MVP to review pull requests.

## Action Items
- [ ] Create new task function to call OpenAI API
- [ ] Design prompt template combining PR data and spirit context
- [ ] Implement response handling and error management
- [ ] Add API response to PR data structure
- [ ] Test with real PR examples

## Notes
This is a simpler alternative to full LangChain integration for the initial MVP. We'll directly call the OpenAI API with a well-structured prompt that includes:
1. Core context and git-cogni spirit guide for personality
2. PR data including commit information and diffs
3. Clear instructions for review format and criteria

This approach will get us to a working MVP faster while still leveraging the context and PR data extraction we've already implemented.

## Estimated Effort
- Hours: 2-3

## Dependencies
- Completed commit processing (✓)
- Completed spirit guide context (✓)
- Python environment with OpenAI package installed 