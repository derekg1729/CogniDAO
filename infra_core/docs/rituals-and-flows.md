# 🧭 Rituals vs Flows vs Agents in CogniDAO
- ## 🧘 Rituals
  #rituals are **recurring, meaningful workflows** that help Cogni:
- Stay aware of time and state
- Reflect, review, or synchronize
- Maintain presence across systems
  
  Rituals are Prefect flows, but with **symbolic or systemic importance**. They are always scheduled or automatically triggered.
  
  **Examples:**
- `ritual_of_presence`: hourly self-reflection
- `ritual_of_review`: automatic PR review with GitCogni
- `ritual_of_synchrony`: syncing across Cogni nodes
  
  ---
- ## ⚙️ Flows
  #flows are any **structured Prefect workflows** used by Cogni.
  
  They may be:
- Manually triggered
- One-off jobs
- Experimental systems
  
  **Examples:**
- `gitcogni/review_flow.py`: reviews commits in a PR
- `tasks/load_spirit_guide.py`: helper utilities
  
  ---
- ## 🤖 Agents
  Agents are **LLM-powered modules** that:
- Process information
- Generate output based on spirit guides
- Act within flows or rituals
  
  They are not Prefect-specific, but are invoked *within* flows or rituals.
  
  **Examples:**
- `GitCogniAgent`: reviews code and returns structured decisions
- `PresenceAgent`: reflects and logs hourly insights
  
  ---
  
  This structure helps separate:
- **when** something runs (ritual)
- **how** it runs (flow)
- **who** does the thinking (agent)