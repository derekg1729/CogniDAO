# Task: Create MVP Prefect Flow for 2-Agent Workflow
:type: Task
:status: todo
:project: [[project-langchain-memory-integration]]

## Current Status
This task defines the creation of a basic Prefect flow within the `experiments/langchain_agents/` directory to orchestrate an MVP 2-agent LangChain workflow, showcasing shared memory usage.

## Action Items
- [ ] Set up basic Prefect flow structure in `experiments/langchain_agents/`.
- [ ] Define a simple LangChain-compatible agent (Agent 1):
  - Introduces a fact into memory (e.g., "The project uses LangChain memory.")
- [ ] Define a second agent (Agent 2):
  - Responds to a question using the fact from shared memory (e.g., "What kind of memory is used?")
- [ ] Implement or mock a basic shared memory mechanism:
  - Should minimally implement `BaseMemory` methods (e.g., wrapping a `dict` or writing to a temporary JSON file)
- [ ] Create `mvp_flow.py` with a `@flow`-decorated function that:
  - Initializes the shared memory
  - Runs Agent 1 → writes to memory
  - Runs Agent 2 → reads from memory
- [ ] Ensure the flow can be executed via `python mvp_flow.py` or `prefect deployment run`

## Test Criteria
- [ ] Flow executes without errors
- [ ] Logs clearly show:
  - Agent 1 writing a fact to memory
  - Agent 2 recalling that fact and using it in its response 