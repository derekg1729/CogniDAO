# AGENTS Guidelines

This repository uses **AGENTS.md** files to guide AI-assisted contributions. Follow these practices unless a nested `AGENTS.md` overrides them.

<agents>
<purpose>CogniDAO repository standards for AI-human software engineering</purpose>
<context>Cogni MCP memory tools are your database for project management + note taking database. Ensure you are working on a clearly defined task, bug, or project, and it is documented.</context>

<core_principles>
  <objective>You will have ONE objective. Know what it is. Is it <feature_planning>, or <debugging>? These require different approaches.</objective>
  <minimal>Minimal, clean changes only. Use existing libraries and functions at all costs. Any custom functions or complexity must be justified</minimal>
  <memory>Use Cogni-Memory MCP with SetContext for branch/namespace</memory>
  <untested>Untested code is untrusted code - add tests for all changes</untested>
  <commits>Commit messages are contracts - accurately reflect each diff</commits>
</core_principles>

<feature_planning>
  <plan_first>ALWAYS start with plan-step before code generation</plan_first>
  <validation>Before ANY code changes, confirm the entire test suite passes. `uv run tox`. Before announcing <feature_complete>, confirm all tests pass again.</validation>
  <context_check>Verify MCP connections and branch context before memory operations</context_check>
  <reference_blocks>
    <agent_playbook>5ad1a0a9-9a2f-4e67-81a8-41299bf41928</agent_playbook>
    <testing_flows>27f9c8bb-cd41-4250-a47d-9dfebc910076</testing_flows>
  </reference_blocks>
  <approach>For complex features, plan approach and confirm with user. List exact files and functions that will be changed.</approach>
</feature_planning>

<testing>
  <command>uv run tox</command>
  <environments>infra_core, mcp_server, web_api, integration, graphs, shared_utils</environments>
  <requirements>All changes require passing tests before commit</requirements>
  <mcp_tools>Test MCP connections and tool functionality</mcp_tools>
  <warning>conftest.py and tox.ini impact cross-environment tests - run full suite after changes</warning>
</testing>

<validation>
  <linting>pre-commit run -a</linting>
  <style>Follow ruff, black, conventional commits</style>
  <functions>Prefer simple, testable functions over classes</functions>
  <integration>ALWAYS test new API routes with integration tests</integration>
  <pull_requests>Reference file lines, ensure tests pass, single topic focus</pull_requests>
</validation>

<debugging>
  <rule>If the user says 'bug', then there is a bug. Everything must be scrutinized. Your job is not done until you find the bug, repro it, and fix it. If you can't find the bug, then you are not doing your job. you are NOT allowed to declare that the code is working.</rule>
  <logs>Check service logs for errors</logs>
  <mcp_status>Verify MCP server connections and tool registry</mcp_status>
  <branch_context>Confirm correct Dolt branch and namespace</branch_context>
  <incremental>Make atomic commits for easier debugging</incremental>
</debugging>

<deployment>
  <setup>./deploy/deploy.sh local</setup>
  <health_checks>Verify all services respond to health endpoints. If you just built a feature/bug, this is the time to curl + test that specific endpoint</health_checks>
</deployment>
</agents>


