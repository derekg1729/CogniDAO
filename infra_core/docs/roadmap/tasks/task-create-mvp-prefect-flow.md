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
- [ ] Replace `MockFileMemory` with the new two-class memory system:
  - [x] Define requirements based on analysis from [[task-analyze-mcp-memory-bank-repo]].
  - [ ] **Implement `CogniMemoryBank` (Core Logic) in `experiments/langchain_agents/cogni_memory_bank.py`:**
    - [ ] Initialize with `memory_bank_root`, `project_name`, `session_id`.
    - [ ] Implement path management (`_get_session_path`, etc.).
    - [ ] Implement internal file I/O helpers (`_read_file`, `_write_file`, `_append_line`).
    - [ ] Implement `write_context(file_name, content, is_json)` method.
    - [ ] Implement `log_decision(decision_data)` method (using `_append_line` to `decisions.jsonl`).
    - [ ] Implement `update_progress(progress_data)` method (using `_write_file` for `progress.json`).
    - [ ] Implement `read_history_dicts()` method (reads `history.json`).
    - [ ] Implement `write_history_dicts(history_dicts)` method (writes `history.json`).
    - [ ] Implement `clear_session()` method (optional: deletes session directory or files).
  - [ ] **Implement `CogniLangchainMemoryAdapter` (LangChain Wrapper) potentially in a new file or same file:**
    - [ ] Inherit from `langchain_core.memory.BaseMemory`.
    - [ ] Initialize with a `CogniMemoryBank` instance.
    - [ ] Implement `memory_variables` property (returning `["history"]`).
    - [ ] Implement `load_memory_variables({})` using `cogni_memory_bank.read_history_dicts()` and `messages_from_dict`.
    - [ ] Implement `save_context(inputs, outputs)` using `messages_to_dict` and `cogni_memory_bank.write_history_dicts()`.
    - [ ] Implement `clear()` using `cogni_memory_bank.clear_session()`.
  - [ ] Integrate `CogniLangchainMemoryAdapter` into `mvp_flow.py`, passing a configured `CogniMemoryBank` instance to it.

## Test Criteria
- [x] Flow executes without errors using `infra_core.openai_handler` and `MockFileMemory`.
- [x] Logs show state transfer via `MockFileMemory`.
- [ ] Flow executes without errors using `CogniLangchainMemoryAdapter`.
- [ ] `CogniMemoryBank` methods create/update files/directories correctly (`history.json`, `decisions.jsonl`, `progress.json`) within the `_memory_banks_experiment/<project_name>/<session_id>/` structure.
- [ ] Files contain expected context/history in appropriate format (JSON, JSONL). 