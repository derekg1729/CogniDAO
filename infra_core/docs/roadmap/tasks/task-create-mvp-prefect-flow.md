# Task: Create MVP Prefect Flow for 2-Agent Workflow
:type: Task
:status: in-progress
:project: [[project-langchain-memory-integration]]

## Current Status
The Prefect flow (`mvp_flow.py`) successfully orchestrates a 2-agent interaction using `infra_core.openai_handler`. State is passed using `MockFileMemory`. The next step is to implement a new memory adapter, `FileMemoryBank`, based on the design patterns from the `alioshr/memory-bank-mcp` TypeScript repository ([https://github.com/alioshr/memory-bank-mcp](https://github.com/alioshr/memory-bank-mcp)). This requires analysis of the reference repo (see [[task-analyze-mcp-memory-bank-repo]]) before implementing the Python equivalent.

## Action Items
- [x] Set up basic Prefect flow structure in `experiments/langchain_agents/` (`mvp_flow.py`)
- [x] Define Agent 1 & 2 logic using `openai_handler` in `mvp_flow.py`.
- [x] Implement mock shared memory mechanism (`MockFileMemory` in `mvp_flow.py`).
- [x] Create `mvp_flow.py` with a `@flow`-decorated function.
- [x] Ensure flow execution via `python -m experiments.langchain_agents.mvp_flow`.
- [ ] Replace `MockFileMemory` with the new two-class memory system:
  - [x] Define requirements based on analysis from [[task-analyze-mcp-memory-bank-repo]].
  - [x] **Implement `FileMemoryBank` (Core Logic) in `experiments/langchain_agents/cogni_memory_bank.py`:**
    - [x] Initialize with `memory_bank_root`, `project_name`, `session_id`.
    - [x] Implement path management (`_get_session_path`, etc.).
    - [x] Implement internal file I/O helpers (`_read_file`, `_write_file`, `_append_line`).
    - [x] Implement `write_context(file_name, content, is_json)` method.
    - [x] Implement `log_decision(decision_data)` method (using `_append_line` to `decisions.jsonl`).
    - [x] Implement `update_progress(progress_data)` method (using `_write_file` for `progress.json`).
    - [x] Implement `read_history_dicts()` method (reads `history.json`).
    - [x] Implement `write_history_dicts(history_dicts)` method (writes `history.json`).
    - [x] Implement `clear_session()` method (optional: deletes session directory or files).
  - [x] **Implement `CogniLangchainMemoryAdapter` (LangChain Wrapper) potentially in a new file or same file:**
    - [x] Inherit from `langchain_core.memory.BaseMemory`.
    - [x] Initialize with a `FileMemoryBank` instance.
    - [x] Implement `memory_variables` property (returning `["history"]`).
    - [x] Implement `load_memory_variables({})` using `cogni_memory_bank.read_history_dicts()` and `messages_from_dict`.
    - [x] Implement `save_context(inputs, outputs)` using `messages_to_dict` and `cogni_memory_bank.write_history_dicts()`.
    - [x] Implement `clear()` using `cogni_memory_bank.clear_session()`.
  - [x] Integrate `CogniLangchainMemoryAdapter` into `mvp_flow.py`, passing a configured `FileMemoryBank` instance to it.

## Test Criteria
- [x] Flow executes without errors using `infra_core.openai_handler` and `MockFileMemory`.
- [x] Logs show state transfer via `MockFileMemory`.
- [x] Flow executes without errors using `CogniLangchainMemoryAdapter` (tested via direct script execution).
- [x] `FileMemoryBank` methods create/update files/directories correctly (`history.json`, `decisions.jsonl`, `progress.json`) within the `_memory_banks_experiment/<project_name>/<session_id>/` structure (verified by local tests and flow run).
- [x] Files contain expected context/history in appropriate format (JSON, JSONL) (verified by local tests and flow run). 