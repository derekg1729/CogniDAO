---
:type: Task
:status: todo
:project: gitcogni-local-models
:created: {datetime.datetime.utcnow().strftime('%Y-%m-%d')}
---

# Split GitCogni into Commit and Verdict Agents (Shallow Modular Refactor)

## Goal
Preserve GitCogni's current behavior while modularizing commit and final verdict logic into agent-like components, allowing model and spirit overrides per phase.

## Constraints
- Do NOT overengineer. Match existing class and flow structure closely.
- Avoid agent orchestration frameworks or spirit routing logic (for now).
- Preserve Prefect flow interface and memory integration.

## Phases

### Minimal Modular Refactor
- [ ] Extract commit review loop into `CommitReviewPhase.run(commits, context) -> List[CommitReview]`.
- [ ] Extract final verdict prompt into `VerdictPhase.run(commit_reviews, pr_info, context) -> str`.
- [ ] Accept model handler and spirit guide at construction per phase.
- [ ] Inject `CommitReviewPhase` and `VerdictPhase` into `GitCogniAgent` constructor with defaults if not passed.
- [ ] Refactor `GitCogniAgent.review_pr()` to delegate commit reviews and verdict to those injected phases.
- [ ] Ensure logs clearly indicate which model is used per phase (commit vs. verdict).

### Hybrid Model Support
- [ ] Update flow to optionally use DeepSeek for commit reviews and Mistral/LLaMA3 for verdict phase.
- [ ] Accept CLI/env override for model-per-phase: e.g. `--commit-model=deepseek --verdict-model=llama3.1`.
- [ ] Verify both handlers use the same interface (BaseModelHandler) and schema.

### Testing
- [ ] Test hybrid config on a small PR with both DeepSeek and Mistral locally running.
- [ ] Validate correct model routing and spirit guide application.
- [ ] Log model-specific tokens used per phase.

## Success Criteria
- Code review and verdict stages now clearly separated as injectable phase classes.
- GitCogniAgent behavior unchanged from CLI and Prefect flow perspective.
- User can swap commit and verdict models independently.
- Output logs identify which model handled each stage. 