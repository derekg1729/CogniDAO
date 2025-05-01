---
:type: Project
:status: planning
:epic: Reflexive_Git
---

# GitCogni Local Models

## Description
Enable GitCogni to work with local LLM models like DeepSeek through Ollama or LM Studio, reducing API costs and allowing offline operation while maintaining review quality.

## Implementation Flow
- [ ] Task: Enable Local Model Inference for GitCogni using DeepSeek
- [ ] Task: Benchmarking and Optimization for Local Model Integration
- [ ] Task: Documentation and Setup Guide for Local Model Usage

## Success Criteria
- GitCogni can run end-to-end with local models without API keys
- Performance within 2x of OpenAI API latency for small PRs
- Comparable review quality between local and cloud models
- Simple configuration toggle between local and cloud backends 