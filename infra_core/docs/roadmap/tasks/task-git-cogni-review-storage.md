# Task: Implement Review Formatting
:type: Task
:status: todo
:project: [[project-git-cogni-agent]]
:owner:

## Description
Create markdown formatting for GitCogni review outputs.

## Action Items
- [ ] Define simple Python dictionary structure for commit reviews
- [ ] Create markdown template string for individual commit reviews
- [ ] Implement PR summary markdown generator with severity categorization
- [ ] Add final review decision formatting (approve/request changes)

## Notes
Instead of implementing dedicated storage, we'll use simple in-memory data structures (lists, dictionaries) passed between Prefect tasks. The final output will be markdown text generated directly within the flow.

This task is dependent on having the LLM integration (either direct OpenAI or LangChain) completed first.

## Estimated Effort
- Hours: 1

## Dependencies
- Completed LLM integration (Direct OpenAI or LangChain)
- Completed commit processing (✓)
- Completed spirit guide context (✓)