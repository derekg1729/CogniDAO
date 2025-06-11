#!/usr/bin/env python3
"""
Simple Math Server - Local MCP Tool for Testing
Follows the SaM-92/mcp_autogen_sse_stdio reference pattern

Provides basic arithmetic operations via MCP stdio transport
Used to validate MCP protocol handshake before integrating Cogni tools
"""

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP()


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    print(f"Adding {a} + {b} = {a + b}")
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers together"""
    print(f"Multiplying {a} × {b} = {a * b}")
    return a * b


@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract second number from first"""
    print(f"Subtracting {a} - {b} = {a - b}")
    return a - b


@mcp.tool()
def divide(a: int, b: int) -> float:
    """Divide first number by second (returns float)"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    result = a / b
    print(f"Dividing {a} ÷ {b} = {result}")
    return result


if __name__ == "__main__":
    print("🧮 Math Server starting on stdio transport...")
    # Use stdio transport like the reference implementation
    mcp.run(transport="stdio")
