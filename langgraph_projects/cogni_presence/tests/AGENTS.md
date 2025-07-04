# LangGraph Test Cheat-Sheet  
**Goal:** deterministic, cheap, thorough.  

## Pyramid  
• **Unit** – node func only (pytest + FakeListLLM)  
• **Component** – compiled graph w/ stub nodes; assert route & state  
• **E2E** – LangSmith `evaluate()` / pytest-plugin vs golden dataset  

## Design for Test  
• Inject LLM/tools; expose `build_graph(agent_node=…)` factory  
• Call `graph.nodes['x'].invoke()` directly for fast node tests  

## Determinism  
• `temperature=0`, fixed RNG seeds  
• Cache model calls (LangSmith cassettes)  

## Mock LLM  
• `FakeListLLM` / `FakeChatModel` for predictable outputs  
• Subclass to capture prompts if needed  

## Assertions  
• Verify edge taken & side-effects (DB write, Redis checkpoint)  
• Edge-case drills: resume-checkpoint, tool failure, concurrent invokes  

## CI One-Liner  
```bash
pytest -q && pytest -m eval tests/e2e
