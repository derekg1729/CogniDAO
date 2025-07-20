# AGENTS Guidelines: MCP Server

<agents>
<scope>MCP protocol implementation and Cogni-Memory tool registry</scope>

<core_principles>
  <protocol>MCP protocol compliance for all tools</protocol>
  <isolation>Handle branch and namespace isolation correctly</isolation>
  <schemas>Validate all input/output schemas rigorously</schemas>
  <fallbacks>Graceful error handling for Dolt connection issues</fallbacks>
</core_principles>

<feature_planning>
  <tools>Register all new tools in tool_registry.py</tools>
  <parameters>JSON string parameters in input field format</parameters>
  <namespaces>Plan branch/namespace context management</namespaces>
  <dolt_operations>Consider Dolt working set state for all operations</dolt_operations>
</feature_planning>

<testing>
  <command>uv run tox -e mcp_server</command>
  <mcp_integration>Test MCP protocol compliance and connections</mcp_integration>
  <tool_validation>Verify tool parameter handling and responses</tool_validation>
  <branch_isolation>Test namespace separation and context switching</branch_isolation>
  <schema_tests>Validate schema generation and visibility</schema_tests>
</testing>

<validation>
  <input_normalization>Ensure JSON parameters properly normalized</input_normalization>
  <dolt_status>Validate Dolt working set before operations</dolt_status>
  <schema_visibility>Confirm schemas available to MCP clients</schema_visibility>
  <error_responses>Proper error formatting for MCP protocol</error_responses>
</validation>

<debugging>
  <mcp_logs>Check MCP server connection and tool execution logs</mcp_logs>
  <tool_errors>Validate tool parameter formats and execution</tool_errors>
  <dolt_state>Query Dolt status for branch/namespace conflicts</dolt_state>
  <connection_test>Use MCP client to test tool connectivity</connection_test>
</debugging>
</agents>

Follow the root [AGENTS.md](../../AGENTS.md) for general guidelines.


