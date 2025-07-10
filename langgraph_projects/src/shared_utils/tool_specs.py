"""
Tool Specifications Utilities

Provides utilities for generating tool specifications from MCP tools.
This is shared across agents for consistent tool documentation.

TODO: I feel like we should not have made this module, and this should exist within MCP standard.
"""

from typing import Any, List


def generate_tool_specs_from_mcp_tools(mcp_tools: List[Any]) -> str:
    """
    Generate tool specifications string from MCP tools list

    Args:
        mcp_tools: List of MCP tool objects

    Returns:
        Formatted tool specifications string
    """
    if not mcp_tools:
        return "## Available MCP Tools:\n\nNo tools currently available."
        
    tool_specs = []
    for tool in mcp_tools:
        try:
            # Extract schema information safely
            schema_info = ""
            if hasattr(tool, "schema") and tool.schema and isinstance(tool.schema, dict):
                # Get input schema if available
                input_schema = tool.schema.get("input_schema", {})
                if isinstance(input_schema, dict):
                    properties = input_schema.get("properties", {})
                    required = input_schema.get("required", [])

                    if properties and isinstance(properties, dict):
                        args_info = []
                        for prop_name, prop_details in properties.items():
                            if isinstance(prop_details, dict):
                                prop_type = prop_details.get("type", "unknown")
                                is_required = "(required)" if prop_name in required else "(optional)"
                                args_info.append(f"{prop_name}: {prop_type} {is_required}")
                        if args_info:
                            schema_info = f" | Args: {', '.join(args_info)}"

            # Build concise tool specification
            tool_name = getattr(tool, 'name', 'Unknown')
            tool_desc = getattr(tool, 'description', 'No description')
            tool_spec = f"{tool_name}: {tool_desc}{schema_info}"
            tool_specs.append(tool_spec)
            
        except Exception:
            # Fallback for problematic tools
            tool_name = getattr(tool, 'name', 'Unknown')
            tool_specs.append(f"{tool_name}: Available tool")

    # Create formatted tool specs string (keep under 1.5k tokens)
    tool_specs_text = """## Available MCP Tools:

Example usage:
- navigate: {"url": "https://example.com"}
- screenshot: {"name": "page_capture.png"}

Tools:
""" + "\n".join(f"• {spec}" for spec in tool_specs[:12])  # Limit to top 12 tools

    if len(tool_specs_text) > 1400:  # Trim if too long
        tool_specs_text = tool_specs_text[:1400] + "\n... (more tools available)"

    return tool_specs_text