# Task: Refactor Memory Bank Structure for Clarity and Sharing
:type: Task
:status: todo
:project: [[project-langchain-memory-integration]]
:owner: 

## Description
Reorganize the memory bank structure to eliminate redundancy, improve clarity, and facilitate better memory sharing between agents within a flow. The current structure creates confusing and duplicative directories. The new structure will centralize core documents and group runtime artifacts by flow session.

**Goals:**
1.  Centralize static core documents (Charter, Manifesto, Guides) in one read-only bank.
2.  Ensure agents operating within a flow share a single, dedicated memory bank for that flow session.
3.  Eliminate default, agent-specific memory banks created on agent initialization.
4.  Group all runtime artifacts (history, decisions, agent outputs) logically within the corresponding flow session bank.

## Action Items
- [ ] Modify `CogniAgent.__init__` (`infra_core/cogni_agents/base.py`):
    - [ ] Remove the internal creation of a default `CogniMemoryBank`.
    - [ ] Change signature to accept a `memory: BaseCogniMemory` instance passed during instantiation.
- [ ] Update agent instantiations in flows (e.g., `ritual_of_presence.py`):
    - [ ] Create **one** `CogniMemoryBank` instance per flow run (e.g., `project_name="flows/ritual_of_presence", session_id="ritual-session"`).
    - [ ] Pass this single bank instance to all agents created within that flow.
- [ ] Modify `load_core_context` in `CogniAgent`:
    - [ ] Implement logic to read core documents (Charter, Manifesto, etc.) from a designated central bank (e.g., `project_name="core", session_id="main"`).
    - [ ] Ensure this method *does not* write core documents back to the flow's session bank.
- [ ] Modify `load_spirit` in `CogniAgent`:
    - [ ] Implement logic to read agent-specific spirit guides from the central "core" bank.
    - [ ] Ensure this method *does not* write spirit guides back to the flow's session bank.
- [ ] Verify `record_action` in `CogniAgent`:
    - [ ] Confirm it correctly uses the passed-in session `self.memory` to save `.md` outputs and log decisions within the flow's session directory.
- [ ] Update Unit Tests (`infra_core/cogni_agents/tests/test_base_agent.py`):
    - [ ] Modify `test_agent_initialization` and others to reflect that agents no longer create their own memory banks by default. Tests might need to provide a mock bank during agent init.
    - [ ] Add tests verifying `load_core_context` and `load_spirit` read from the expected "core" bank location (using mocking).
- [ ] Update Integration Tests (`tests/test_ritual_of_presence.py`):
    - [ ] Update `test_flow_creates_memory_files_in_correct_location` to assert files are created in the new `data/memory_banks/flows/ritual_of_presence/ritual-session/` structure.
- [ ] Create seeding mechanism/script for the "core" memory bank:
    - [ ] Script to populate `data/memory_banks/core/main/` with initial versions of Charter, Manifesto, and all spirit guides.
- [ ] Document the new memory bank structure and logic.

## Success Criteria
- [ ] All tests pass (`python test.py`).
- [ ] Running flows (e.g., `ritual_of_presence`) creates memory banks and artifacts only within the `data/memory_banks/flows/<flow_name>/<session_id>/` structure.
- [ ] Agents correctly load core context and spirit guides from the central "core" bank.
- [ ] Agents participating in the same flow run share the same `history.json` and `decisions.jsonl` within the flow's session bank.
- [ ] The default agent memory bank structure (`data/memory_banks/agents/...`) is no longer created automatically.

## Notes
- Requires manual cleanup of existing directories within `data/memory_banks/` before testing the new structure (e.g., remove `agents/`, `core-cogni/`, `git-cogni/` etc.).
- This is a significant refactor impacting agent initialization and context loading.

## Dependencies
- `infra_core.constants` for `MEMORY_BANKS_ROOT`. 