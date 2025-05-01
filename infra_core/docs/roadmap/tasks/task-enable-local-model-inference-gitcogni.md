---
:type: Task
:status: todo
:project: local-models
:name: Enable Local Model Inference for GitCogni using DeepSeek
---

# Current Status
This task is in planning stage. Implementation has not started yet.

## Task Description
Refactor GitCogniAgent to optionally use a local model backend (DeepSeek via Ollama or LM Studio) instead of OpenAI API, using a BaseModelHandler abstraction.

## Phase
MVP: GitCogni Local Model Support

## Action Items
- [ ] Create `BaseModelHandler` interface with `create_chat_completion()` method.
- [ ] Implement `OpenAIModelHandler` that wraps current `create_completion`, `thread_completion`, etc.
- [ ] Implement `LMStudioModelHandler` that sends OpenAI-style POST requests to `http://localhost:1234/v1/chat/completions`.
- [ ] Add `model: BaseModelHandler` field to `CogniAgent` and update `GitCogniAgent` to optionally use it.
- [ ] Refactor `GitCogniAgent.review_pr()` to bypass thread-based flow if `model` is provided, and use direct `chat_completion` calls.
- [ ] Add fallback logic: if `self.model` is not set, fallback to current OpenAI-based thread system.
- [ ] Add a CLI/config flag (`--local-model deepseek`) or `.env` override to toggle backend at runtime.
- [ ] Write a test script to run `gitcogni review_and_save(pr_url)` using a DeepSeek local model through LM Studio.
- [ ] Log and compare runtime + quality of local vs OpenAI inference for 2 small PRs.

## Integration Targets
- `infra_core/openai_handler.py` → replace with BaseModelHandler
- `GitCogniAgent.review_pr` → dual-path: thread-based vs model.create_chat_completion
- Prefect agent runner or CLI launcher → model config injection

## Test Criteria
- GitCogniAgent runs end-to-end with DeepSeek 6.7B in LM Studio
- No errors when switching between local and OpenAI backends
- Reviews saved with clear logs showing which backend was used 