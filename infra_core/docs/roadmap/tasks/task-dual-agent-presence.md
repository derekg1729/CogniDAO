# Task: Implement Dual-Agent Ritual of Presence
:type: Task
:status: completed
:project: [[project-langchain-memory-integration]] # Demonstrates shared memory usage

Enhance the `ritual_of_presence.py` flow to include a second agent (`ReflectionCogniAgent`) that responds to the first agent's (`CoreCogniAgent`) thought using a shared `CogniMemoryBank`, aligning with LangChain memory patterns.

## Action Items
- [x] Define `ReflectionCogniAgent` class in `infra_core/cogni_agents/reflection_cogni.py`.
      - Agent uses `memory_adapter.load_memory_variables` in `prepare_input`.
- [x] Modify `ritual_of_presence_flow` in `infra_core/flows/rituals/ritual_of_presence.py`:
      - Instantiate `CogniMemoryBank` and wrap with `CogniLangchainMemoryAdapter` in the main flow function.
      - Implement shared memory initialization and `adapter.clear()` at flow start.
- [x] Refactor the existing `create_thought` task (rename `create_initial_thought`):
      - Accept the shared memory adapter instance.
      - Instantiate `CoreCogniAgent`.
      - Call `agent.prepare_input()` and `agent.act()`.
      - **Crucially**, call `memory_adapter.save_context()` with the appropriate inputs/outputs to store history in LangChain format.
      - *(Optional)* Call `agent.record_action()` separately to maintain detailed action logs in the memory bank.
- [x] Create a *new* Prefect task function `create_reflection_thought`:
      - Accept the shared memory adapter instance.
      - Instantiate `ReflectionCogniAgent` (passing the adapter).
      - Call `agent.prepare_input()` and `agent.act()`.
      - Call `memory_adapter.save_context()` with appropriate inputs/outputs.
      - *(Optional)* Call `agent.record_action()` separately for detailed logging.
- [x] Adjust the main flow logic in `ritual_of_presence_flow` to:
      - Orchestrate the calls to the two tasks sequentially, passing the shared adapter.
- [x] Adjusted `CoreCogniAgent.act` and `ReflectionCogniAgent.act` to return their results *before* calling `record_action`.
- [ ] Update or add tests for `ritual_of_presence.py` to verify:
      - Both tasks run and use the shared adapter.
      - The memory bank contains `history.json` reflecting the two turns.
      - The memory bank *also* contains the `action_*.md` and `decisions.jsonl` files from `record_action` calls.
      - The reflection content relates to the initial thought content.

## Test Criteria
- The `ritual_of_presence_flow` completes successfully.
- The `infra_core/memory/memory_banks/ritual_of_presence/<session_id>/` directory contains:
    - `history.json` with two turns (initial thought, reflection).
    - Two `action_*.md` files (initial thought, reflection).
    - `decisions.jsonl` with two entries.
- The content of the reflection action/history entry relates to the initial thought action/history entry.

## Current Status
- Implementation complete.
- `ReflectionCogniAgent` defined.
- Flow refactored to use shared memory adapter and `save_context` pattern.
- Manual run successful and verified memory bank output structure.
- Tests still need to be updated/created.

This task is planned. The current `ritual_of_presence.py` uses only a single `CoreCogniAgent`. The `experiments/langchain_agents/mvp_flow.py` serves as a useful reference for implementing shared memory between Prefect tasks wrapping agents. 