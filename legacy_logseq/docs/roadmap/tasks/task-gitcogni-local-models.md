---
:type: Task
:status: in-progress
:project: gitcogni-local-models
:created: 2023-11-06
---

# Enable Local Model Inference for GitCogni using DeepSeek

## Current Status

Implementation is in progress. The core model handler abstractions are complete, and Ollama integration has been implemented and tested with simple examples. Further work is needed to fully integrate with GitCogniAgent.

## Implementation Details

Phase: MVP: GitCogni Local Model Support

### Action Items

- [x] Create `BaseModelHandler` interface with `create_chat_completion()` method
  - Implemented in `legacy_logseq/model_handlers/base.py`
- [x] Implement `OpenAIModelHandler` that wraps current `create_completion`, `thread_completion`, etc.
  - Implemented in `legacy_logseq/model_handlers/openai_handler.py`
- [x] Implement `OllamaModelHandler` for Ollama server with DeepSeek and other models
  - Implemented in `legacy_logseq/model_handlers/ollama_handler.py` (Moved from experiments)
- [x] Add `model: BaseModelHandler` field to `CogniAgent` and update `GitCogniAgent` to optionally use it
  - Implemented in `legacy_logseq/cogni_agents/base.py`
- [ ] Refactor `GitCogniAgent.review_pr()` to bypass thread-based flow if `model` is provided, and use direct `chat_completion` calls
  - Now handled by `task-gitcogni-modular-refactor.md`
- [ ] Add fallback logic: if `self.model` is not set, fallback to current OpenAI-based thread system
  - Now handled by `task-gitcogni-modular-refactor.md`
- [ ] Add a CLI/config flag (`--local-model deepseek`) or `.env` override to toggle backend at runtime
  - Now handled by `task-gitcogni-modular-refactor.md`
- [x] Write a test script to run model inference using a local model
  - Implemented in `experiments/src/examples/simple_ollama_agent.py` (Example agent script)
- [x] Create Docker setup for Ollama integration
  - Implemented in `deploy/ollama_deployment/` directory
- [x] Basic testing of OllamaModelHandler with real Ollama server
- [/] Integrate OllamaModelHandler with GitCogniAgent
  - Started but needs completion in `legacy_logseq/cogni_agents/git_cogni/git_cogni.py` (Example was `experiments/src/examples/gitcogni_with_ollama.py`)
- [ ] Log and compare runtime + quality of local vs OpenAI inference for 2 small PRs

### Integration Targets

- `legacy_logseq/cogni_agents/git_cogni/git_cogni.py` → Use `self.model` attribute if present
- `GitCogniAgent.review_pr` → dual-path: thread-based vs model.create_chat_completion
- Prefect agent runner or CLI launcher → model config injection

## Test Criteria

- [x] OllamaModelHandler passes unit tests
- [x] OllamaModelHandler can connect to Ollama server and generate responses
- [ ] GitCogniAgent runs end-to-end with DeepSeek or other models via Ollama
- [ ] No errors when switching between local and OpenAI backends
- [ ] Reviews saved with clear logs showing which backend was used

## Related Files

- `legacy_logseq/cogni_agents/git_cogni/git_cogni.py`
- `legacy_logseq/openai_handler.py`
- `legacy_logseq/cogni_agents/base.py`
- `legacy_logseq/model_handlers/*.py`
- `experiments/src/examples/simple_ollama_agent.py`
- `deploy/ollama_deployment/docker-compose.yml` 