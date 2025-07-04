## Goal  
Deterministic • cheap • thorough

## Layers  
- **Unit** — call `graph.nodes['foo'].invoke()` with `FakeListLLM` :contentReference[oaicite:0]{index=0}  
- **Component** — compile graph, stub LLM/tool nodes, assert chosen edge + state :contentReference[oaicite:1]{index=1}  
- **E2E** — run `langsmith.evaluate()` or `pytest -m eval` on a golden dataset :contentReference[oaicite:2]{index=2}  

## Determinism  
- Set `temperature=0`, fix RNG seeds, replay LangSmith cassettes :contentReference[oaicite:3]{index=3}  
- Default to `FakeListLLM` for local runs :contentReference[oaicite:4]{index=4}  

## Prompt Contracts  
- Snapshot rendered prompts (e.g., `pytest-approvals`); fail on diff :contentReference[oaicite:5]{index=5}  

## Fault-Tolerance & Concurrency  
- **Resume test:** save Redis/SQLite checkpoint → mutate → `invoke(None)`; expect identical result :contentReference[oaicite:6]{index=6}  
- **Parallel test:** multiple invocations with mock interrupts; assert isolation :contentReference[oaicite:7]{index=7}  

## Cost & Latency Guards  
- Env-caps (`LANGSMITH_BILLING_MAX_USD`, token limits); fail if p95 latency ↑ 15 % :contentReference[oaicite:8]{index=8}  

## Dataset Discipline  
- Store golden `.jsonl` in `tests/data` and version with DVC/Dolt :contentReference[oaicite:9]{index=9}  

## Fuzzing  
- Use `hypothesis` on router nodes to surface unseen paths :contentReference[oaicite:10]{index=10}  

```bash
# CI one-liner
pytest -q && pytest -m eval
