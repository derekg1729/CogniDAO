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
  - Implemented in `infra_core/model_handlers/base.py`
- [x] Implement `OpenAIModelHandler` that wraps current `create_completion`, `thread_completion`, etc.
  - Implemented in `infra_core/model_handlers/openai_handler.py`
- [x] Implement `LMStudioModelHandler` that sends OpenAI-style POST requests to `http://localhost:1234/v1/chat/completions`
  - Implemented in `infra_core/model_handlers/lmstudio_handler.py`
- [x] Implement `OllamaModelHandler` for Ollama server with DeepSeek and other models
  - Implemented in `experiments/src/core/models/ollama_model_handler.py`
- [ ] Add `model: BaseModelHandler` field to `CogniAgent` and update `GitCogniAgent` to optionally use it
- [ ] Refactor `GitCogniAgent.review_pr()` to bypass thread-based flow if `model` is provided, and use direct `chat_completion` calls
- [ ] Add fallback logic: if `self.model` is not set, fallback to current OpenAI-based thread system
- [ ] Add a CLI/config flag (`--local-model deepseek`) or `.env` override to toggle backend at runtime
- [x] Write a test script to run model inference using a local model
  - Implemented in `experiments/src/examples/use_ollama_handler.py`
- [x] Create Docker setup for Ollama integration
  - Implemented in `experiments/src/scripts/` directory
- [x] Basic testing of OllamaModelHandler with real Ollama server
- [ ] Integrate OllamaModelHandler with GitCogniAgent
  - Started with `experiments/src/examples/gitcogni_with_ollama.py` but needs further work
- [ ] Log and compare runtime + quality of local vs OpenAI inference for 2 small PRs

### Integration Targets

- `infra_core/openai_handler.py` → replace with BaseModelHandler
- `GitCogniAgent.review_pr` → dual-path: thread-based vs model.create_chat_completion
- Prefect agent runner or CLI launcher → model config injection

## Test Criteria

- [x] OllamaModelHandler passes unit tests
- [x] OllamaModelHandler can connect to Ollama server and generate responses
- [ ] GitCogniAgent runs end-to-end with DeepSeek or other models via Ollama
- [ ] No errors when switching between local and OpenAI backends
- [ ] Reviews saved with clear logs showing which backend was used

## Related Files

- `infra_core/cogni_agents/git_cogni/git_cogni.py`
- `infra_core/openai_handler.py`
- `infra_core/cogni_agents/base.py`
- `infra_core/model_handlers/*.py`
- `experiments/src/core/models/ollama_model_handler.py` 