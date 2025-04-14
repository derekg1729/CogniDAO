# Task: Implement Dual-Agent Ritual of Presence
:type: Task
:status: todo
:project: [[project-langchain-memory-integration]] # Demonstrates shared memory usage

Enhance the `ritual_of_presence.py` flow to include a second agent (`ReflectionCogniAgent`) that responds to the first agent's (`CoreCogniAgent`) thought using a shared `CogniMemoryBank`, aligning with LangChain memory patterns.

## Action Items
- [x] Define `ReflectionCogniAgent` class in `infra_core/cogni_agents/reflection_cogni.py`.
      - Agent uses `memory_adapter.load_memory_variables` in `prepare_input`.
- [ ] Modify `ritual_of_presence_flow` in `infra_core/flows/rituals/ritual_of_presence.py`:
      - Instantiate `CogniMemoryBank` and wrap with `CogniLangchainMemoryAdapter` in the main flow function.
      - Implement shared memory initialization and `adapter.clear()` at flow start.
- [ ] Refactor the existing `create_thought` task (rename `create_initial_thought`):
      - Accept the shared memory adapter instance.
      - Instantiate `CoreCogniAgent`.
      - Call `agent.prepare_input()` and `agent.act()`.
      - **Crucially**, call `memory_adapter.save_context()` with the appropriate inputs/outputs to store history in LangChain format.
      - *(Optional)* Call `agent.record_action()` separately to maintain detailed action logs in the memory bank.
- [ ] Create a *new* Prefect task function `create_reflection_thought`:
      - Accept the shared memory adapter instance.
      - Instantiate `ReflectionCogniAgent` (passing the adapter).
      - Call `agent.prepare_input()` and `agent.act()`.
      - Call `memory_adapter.save_context()` with appropriate inputs/outputs.
      - *(Optional)* Call `agent.record_action()` separately for detailed logging.
- [ ] Adjust the main flow logic in `ritual_of_presence_flow` to:
      - Orchestrate the calls to the two tasks sequentially, passing the shared adapter.
- [ ] *(Potentially Needed)* Adjust `CoreCogniAgent.act` and `ReflectionCogniAgent.act` to return their results *before* calling `record_action` (if they currently call it internally). The task wrappers should ideally handle the saving.
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
- `ReflectionCogniAgent` defined.
- Task refactoring and flow modification pending.
- Alignment with LangChain `save_context` pattern is the key change.

This task is planned. The current `ritual_of_presence.py` uses only a single `CoreCogniAgent`. The `experiments/langchain_agents/mvp_flow.py` serves as a useful reference for implementing shared memory between Prefect tasks wrapping agents. 