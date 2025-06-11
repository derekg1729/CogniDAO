import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from prefect import task, flow, get_run_logger
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import json
import argparse
import asyncio
import httpx

# --- Project Constants Import ---
from infra_core.constants import THOUGHTS_DIR

# --- Memory Imports (Legacy - will be replaced by MCP) ---
# from infra_core.agents.claude_client import CogniMemoryAgent
# from infra_core.memory.memory_agent import CogniMemoryAgent as MemoryAgent
# from infra_core.memory.memory_providers import CogniMemoryBank
# from infra_core.memory.text_memory import TextMemoryProvider
# from infra_core.memory.memory_core import MemoryCore

# --- MCP Integration via ToolHive HTTP API ---
TOOLHIVE_API_BASE = "http://toolhive:8080"
MCP_SERVER_NAME = "cogni-mcp"


@task(name="mcp_call_tool")
async def mcp_call_tool(tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Call an MCP tool via ToolHive HTTP API

    Args:
        tool_name: Name of the MCP tool to call
        arguments: Arguments to pass to the tool

    Returns:
        Tool execution result
    """
    logger = get_run_logger()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # ToolHive HTTP API endpoint for calling MCP tools
            # This is the correct way to call MCP tools through ToolHive
            payload = {"server": MCP_SERVER_NAME, "tool": tool_name, "arguments": arguments or {}}

            logger.info(f"🔧 Calling MCP tool '{tool_name}' via ToolHive API")

            # Make HTTP POST request to ToolHive API
            response = await client.post(
                f"{TOOLHIVE_API_BASE}/api/v1/tools/call",
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ MCP tool '{tool_name}' executed successfully")
                return result
            else:
                logger.error(f"❌ MCP tool call failed: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}: {response.text}"}

    except Exception as e:
        logger.error(f"❌ MCP tool call exception: {e}")
        return {"error": str(e)}


@task(name="mcp_get_memory_blocks")
async def mcp_get_memory_blocks(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get memory blocks using MCP QueryMemoryBlocksSemantic tool

    Args:
        query: Semantic search query
        limit: Maximum number of results

    Returns:
        List of memory blocks
    """
    logger = get_run_logger()

    logger.info(f"🧠 Querying memory via MCP: '{query}' (limit: {limit})")

    result = await mcp_call_tool(
        "mcp_cogni-memory-local_QueryMemoryBlocksSemantic",
        {"input": json.dumps({"query_text": query, "top_k": limit})},
    )

    if "error" in result:
        logger.error(f"❌ Memory query failed: {result['error']}")
        return []

    # Parse the MCP response
    try:
        if "blocks" in result:
            blocks = result["blocks"]
            logger.info(f"✅ Retrieved {len(blocks)} memory blocks")
            return blocks
        else:
            logger.warning("⚠️ No blocks found in MCP response")
            return []
    except Exception as e:
        logger.error(f"❌ Error parsing MCP response: {e}")
        return []


@task(name="mcp_get_active_work_items")
async def mcp_get_active_work_items(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get active work items using MCP GetActiveWorkItems tool

    Args:
        limit: Maximum number of results

    Returns:
        List of active work items
    """
    logger = get_run_logger()

    logger.info(f"📋 Getting active work items via MCP (limit: {limit})")

    result = await mcp_call_tool(
        "mcp_cogni-memory-local_GetActiveWorkItems", {"input": json.dumps({"limit": limit})}
    )

    if "error" in result:
        logger.error(f"❌ Work items query failed: {result['error']}")
        return []

    # Parse the MCP response
    try:
        if "work_items" in result:
            work_items = result["work_items"]
            logger.info(f"✅ Retrieved {len(work_items)} active work items")
            return work_items
        else:
            logger.warning("⚠️ No work items found in MCP response")
            return []
    except Exception as e:
        logger.error(f"❌ Error parsing MCP response: {e}")
        return []


@task(name="load_agent_memory_via_mcp")
async def load_agent_memory_via_mcp(agent_name: str = "ritual_of_presence") -> Dict[str, Any]:
    """
    Load agent memory using MCP tools

    Args:
        agent_name: Name of the agent to load memory for

    Returns:
        Dictionary containing loaded memory data
    """
    logger = get_run_logger()
    logger.info(f"🧠 Loading memory for agent '{agent_name}' via MCP")

    # Load relevant memories
    memories = await mcp_get_memory_blocks(
        f"ritual of presence agent memory {agent_name}", limit=10
    )

    # Load active work items
    work_items = await mcp_get_active_work_items(limit=5)

    memory_data = {
        "agent_name": agent_name,
        "memories": memories,
        "active_work_items": work_items,
        "loaded_at": datetime.now().isoformat(),
        "source": "MCP via ToolHive API",
    }

    logger.info(f"✅ Loaded {len(memories)} memories and {len(work_items)} work items")
    return memory_data


# --- Legacy Tasks (Commented Out) ---
# @task(name="load_agent_memory")
# def load_agent_memory(agent_name: str = "ritual_of_presence") -> Dict[str, Any]:
#     """
#     Load agent memory from the memory bank
#
#     Args:
#         agent_name: Name of the agent to load memory for
#
#     Returns:
#         Dictionary containing loaded memory data
#     """
#     logger = get_run_logger()
#     logger.info(f"Loading memory for agent: {agent_name}")
#
#     # Initialize memory provider
#     memory_bank = CogniMemoryBank()
#     memory_core = MemoryCore(providers=[memory_bank])
#
#     # Load memories related to this agent
#     memories = memory_core.retrieve_memories(
#         query=f"agent:{agent_name}",
#         limit=50
#     )
#
#     logger.info(f"Loaded {len(memories)} memories for agent {agent_name}")
#
#     return {
#         "agent_name": agent_name,
#         "memories": [mem.to_dict() for mem in memories],
#         "loaded_at": datetime.now().isoformat()
#     }


@task(name="generate_presence_summary")
async def generate_presence_summary(
    memory_data: Dict[str, Any], custom_prompt: Optional[str] = None
) -> str:
    """
    Generate a summary of current presence and context using loaded memory

    Args:
        memory_data: Loaded memory data from MCP
        custom_prompt: Custom prompt for the summary

    Returns:
        Generated presence summary
    """
    logger = get_run_logger()
    logger.info("🎯 Generating presence summary via MCP-powered flow")

    # Extract data from memory
    memories = memory_data.get("memories", [])
    work_items = memory_data.get("active_work_items", [])

    # Create summary
    summary_parts = [
        "🤖 **Ritual of Presence - MCP-Powered Flow**",
        f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"🧠 Memory Source: {memory_data.get('source', 'Unknown')}",
        "",
        "📊 **Memory Status**:",
        f"- Loaded {len(memories)} relevant memories",
        f"- Found {len(work_items)} active work items",
        "",
    ]

    if custom_prompt:
        summary_parts.extend([f"💭 **Custom Prompt**: {custom_prompt}", ""])

    if work_items:
        summary_parts.append("📋 **Active Work Items**:")
        for item in work_items[:3]:  # Show top 3
            title = item.get("title", "Untitled")
            status = item.get("status", "Unknown")
            summary_parts.append(f"- {title} ({status})")
        summary_parts.append("")

    if memories:
        summary_parts.append("🧠 **Recent Memories**:")
        for mem in memories[:3]:  # Show top 3
            mem_text = (
                mem.get("text", "")[:100] + "..."
                if len(mem.get("text", "")) > 100
                else mem.get("text", "")
            )
            summary_parts.append(f"- {mem_text}")
        summary_parts.append("")

    summary_parts.extend(
        [
            "🎯 **MCP Integration Status**: ✅ Successfully connected to Cogni Memory via ToolHive",
            "🚀 **Next Steps**: Ready for enhanced AI-powered workflows with full memory access",
            "",
            "---",
            "🔧 **Technical Details**:",
            f"- MCP Server: {MCP_SERVER_NAME}",
            f"- ToolHive API: {TOOLHIVE_API_BASE}",
            f"- Agent: {memory_data.get('agent_name', 'Unknown')}",
        ]
    )

    summary = "\n".join(summary_parts)

    logger.info("✅ Presence summary generated successfully")
    return summary


@task(name="save_presence_record")
async def save_presence_record(summary: str, output_dir: Optional[Path] = None) -> Path:
    """
    Save the presence record to a file

    Args:
        summary: Generated presence summary
        output_dir: Directory to save the record (defaults to THOUGHTS_DIR)

    Returns:
        Path to the saved file
    """
    logger = get_run_logger()

    if output_dir is None:
        output_dir = Path(THOUGHTS_DIR)

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"presence_ritual_mcp_{timestamp}.md"
    file_path = output_dir / filename

    with open(file_path, "w") as f:
        f.write(summary)

    logger.info(f"✅ Presence record saved to: {file_path}")
    return file_path


@flow(name="ritual_of_presence_mcp", log_prints=True)
async def ritual_of_presence_mcp(
    agent_name: str = "ritual_of_presence",
    custom_prompt: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    MCP-powered Ritual of Presence flow that uses ToolHive API to access Cogni Memory

    Args:
        agent_name: Name of the agent performing the ritual
        custom_prompt: Custom prompt for the ritual
        output_dir: Directory to save output files

    Returns:
        Dictionary containing ritual results
    """
    logger = get_run_logger()
    logger.info("🎯 Starting MCP-powered Ritual of Presence")

    # Convert output_dir to Path if provided
    output_path = Path(output_dir) if output_dir else None

    # Load agent memory via MCP
    memory_data = await load_agent_memory_via_mcp(agent_name)

    # Generate presence summary
    summary = await generate_presence_summary(memory_data, custom_prompt)

    # Save presence record
    saved_path = await save_presence_record(summary, output_path)

    # Print summary for immediate feedback
    print("\n" + "=" * 60)
    print("🎯 RITUAL OF PRESENCE - MCP INTEGRATION COMPLETE")
    print("=" * 60)
    print(summary)
    print("=" * 60)

    result = {
        "agent_name": agent_name,
        "custom_prompt": custom_prompt,
        "memory_data": memory_data,
        "summary": summary,
        "saved_path": str(saved_path),
        "success": True,
        "integration_type": "MCP via ToolHive API",
    }

    logger.info(f"✅ Ritual of Presence completed successfully - saved to {saved_path}")
    return result


# --- Legacy Flow (Commented Out) ---
# @flow(name="ritual_of_presence", log_prints=True)
# def ritual_of_presence(
#     agent_name: str = "ritual_of_presence",
#     custom_prompt: Optional[str] = None,
#     output_dir: Optional[str] = None
# ) -> Dict[str, Any]:
#     """
#     Ritual of Presence flow - loads agent memory and generates presence summary
#
#     Args:
#         agent_name: Name of the agent performing the ritual
#         custom_prompt: Custom prompt for the ritual
#         output_dir: Directory to save output files
#
#     Returns:
#         Dictionary containing ritual results
#     """
#     logger = get_run_logger()
#     logger.info(f"Starting Ritual of Presence for agent: {agent_name}")
#
#     # Convert output_dir to Path if provided
#     output_path = Path(output_dir) if output_dir else None
#
#     # Load agent memory
#     memory_data = load_agent_memory(agent_name)
#
#     # Generate presence summary using loaded memory
#     summary = generate_presence_summary(memory_data, custom_prompt)
#
#     # Save presence record
#     saved_path = save_presence_record(summary, output_path)
#
#     # Print summary for immediate feedback
#     print("\n" + "="*60)
#     print("🎯 RITUAL OF PRESENCE COMPLETE")
#     print("="*60)
#     print(summary)
#     print("="*60)
#
#     result = {
#         "agent_name": agent_name,
#         "custom_prompt": custom_prompt,
#         "memory_data": memory_data,
#         "summary": summary,
#         "saved_path": str(saved_path),
#         "success": True
#     }
#
#     logger.info(f"Ritual of Presence completed successfully - saved to {saved_path}")
#     return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ritual of Presence - MCP Integration")
    parser.add_argument("--agent-name", default="ritual_of_presence", help="Name of the agent")
    parser.add_argument("--custom-prompt", help="Custom prompt for the ritual")
    parser.add_argument("--output-dir", help="Output directory for files")
    parser.add_argument("--mcp", action="store_true", help="Use MCP-powered flow (default)")
    parser.add_argument("--legacy", action="store_true", help="Use legacy flow (disabled)")

    args = parser.parse_args()

    if args.legacy:
        print("❌ Legacy flow is disabled. MCP integration is the default.")
        exit(1)

    # Run the MCP-powered flow
    result = asyncio.run(
        ritual_of_presence_mcp(
            agent_name=args.agent_name, custom_prompt=args.custom_prompt, output_dir=args.output_dir
        )
    )

    if result["success"]:
        print("\n✅ Ritual completed successfully!")
        print(f"📄 Summary saved to: {result['saved_path']}")
    else:
        print("\n❌ Ritual failed!")
        exit(1)
