# docker-compose-infra
:type: Project
:status: todo
:project: [[Epic_Presence_and_Control_Loops]]

## Description
Package all services (Prefect, Ollama, MCP, Git-Cogni agents) into a `docker-compose.yml` stack with health checks and shared volume.

## Steps
- [ ] Write Dockerfiles for each agent
- [ ] Define service dependencies
- [ ] Enable volume sharing & logging
- [ ] Optional: Add heartbeat via Prefect schedule
