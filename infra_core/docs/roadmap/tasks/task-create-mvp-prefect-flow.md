# Task: Create MVP Prefect Flow for 2-Agent Workflow
:type: Task
:status: in-progress
:project: [[project-langchain-memory-integration]]

## Current Status
The Prefect flow (`mvp_flow.py`) successfully orchestrates a 2-agent interaction using `infra_core.openai_handler`. State is passed using `MockFileMemory`. The next step is to implement a new memory adapter, `CogniMemoryBank`, based on the design patterns from the `alioshr/memory-bank-mcp` TypeScript repository ([https://github.com/alioshr/memory-bank-mcp](https://github.com/alioshr/memory-bank-mcp)). This requires analysis of the reference repo (see [[task-analyze-mcp-memory-bank-repo]]) before implementing the Python equivalent.

## Action Items
- [x] Set up basic Prefect flow structure in `experiments/langchain_agents/` (`mvp_flow.py`)
- [x] Define Agent 1 & 2 logic using `openai_handler` in `mvp_flow.py`.
- [x] Implement mock shared memory mechanism (`MockFileMemory` in `mvp_flow.py`).
- [x] Create `mvp_flow.py` with a `@flow`-decorated function.
- [x] Ensure flow execution via `python -m experiments.langchain_agents.mvp_flow`.
- [ ] Replace `MockFileMemory` with `CogniMemoryBank` implementation (Python equivalent of `memory-bank-mcp` design):
  - [ ] Define requirements based on analysis from [[task-analyze-mcp-memory-bank-repo]].
  - [ ] Create `experiments/langchain_agents/cogni_memory_bank.py`.
  - [ ] Implement `BaseMemory` interface (`load_memory_variables`, `save_context`, `clear`).
  - [ ] Implement core logic mirroring `memory-bank-mcp` (file layout, session tracking, context writing, decision logging etc.).
  - [ ] Integrate `CogniMemoryBank` into `mvp_flow.py`.

## Test Criteria
- [x] Flow executes without errors using `infra_core.openai_handler` and `MockFileMemory`.
- [x] Logs show state transfer via `MockFileMemory`.
- [ ] Flow executes without errors using `CogniMemoryBank`.
- [ ] `CogniMemoryBank` creates files/directories mirroring the structure observed in `memory-bank-mcp`.
- [ ] Files created by `CogniMemoryBank` contain expected context/history in appropriate format (Markdown/JSON). 