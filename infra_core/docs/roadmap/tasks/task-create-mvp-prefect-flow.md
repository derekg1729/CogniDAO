# Task: Create MVP Prefect Flow for 2-Agent Workflow
:type: Task
:status: in-progress
:project: [[project-langchain-memory-integration]]

## Current Status
Basic Prefect flow structure (`mvp_flow.py`) created in `experiments/langchain_agents/`. Includes a mock `BaseMemory` implementation (`MockFileMemory`) using a temporary JSON file and placeholder agent functions. The flow successfully runs end-to-end, demonstrating task orchestration and basic memory interaction (Agent 1 writes, Agent 2 reads).

## Action Items
- [x] Set up basic Prefect flow structure in `experiments/langchain_agents/` (`mvp_flow.py`)
- [/] Define a simple LangChain-compatible agent (Agent 1): (`run_agent` placeholder in `mvp_flow.py`)
  - Introduces a fact into memory (e.g., "The project uses LangChain memory.")
- [/] Define a second agent (Agent 2): (`run_agent` placeholder in `mvp_flow.py`)
  - Responds to a question using the fact from shared memory (e.g., "What kind of memory is used?")
- [x] Implement or mock a basic shared memory mechanism: (`MockFileMemory` in `mvp_flow.py`)
  - Should minimally implement `BaseMemory` methods (e.g., wrapping a `dict` or writing to a temporary JSON file)
- [x] Create `mvp_flow.py` with a `@flow`-decorated function that:
  - Initializes the shared memory
  - Runs Agent 1 → writes to memory
  - Runs Agent 2 → reads from memory
- [x] Ensure the flow can be executed via `python mvp_flow.py` or `prefect deployment run`

## Test Criteria
- [x] Flow executes without errors
- [x] Logs clearly show:
  - Agent 1 writing a fact to memory
  - Agent 2 recalling that fact and using it in its response 