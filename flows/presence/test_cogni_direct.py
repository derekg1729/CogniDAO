#!/usr/bin/env python3
"""
Simple test: AutoGen + Cogni Memory Direct Access
Bypass ToolHive complexity and connect directly to memory system

This tests if our memory tools work with AutoGen without container orchestration
"""

import asyncio
import logging
import os

# AutoGen core imports
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Cogni memory imports - direct access
try:
    from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
    from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
    from infra_core.agents.memory_specialist import MemorySpecialist

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    print("✅ Successfully imported Cogni memory system")
except ImportError as e:
    print(f"❌ Failed to import Cogni memory system: {e}")
    exit(1)


async def test_direct_memory_access():
    """Test direct access to Cogni memory system"""
    print("🧪 Testing direct Cogni memory access...")

    try:
        # Try to connect directly to the database
        dolt_config = DoltConnectionConfig(
            host="localhost",
            port=3306,
            user="root",
            password=os.environ.get("DOLT_ROOT_PASSWORD", ""),
            database="cogni-dao-memory",
        )

        print(f"🔗 Connecting to database: {dolt_config.host}:{dolt_config.port}")

        # Initialize memory bank
        memory_bank = StructuredMemoryBank(
            chroma_path="/tmp/test_cogni_chroma",
            chroma_collection="test_collection",
            dolt_connection_config=dolt_config,
        )

        # Create a memory specialist agent
        model_client = OpenAIChatCompletionClient(model="gpt-4o")

        memory_specialist = MemorySpecialist(
            name="memory_specialist",
            model_client=model_client,
            memory_bank=memory_bank,
        )

        print("✅ Direct memory access working!")
        print(f"Memory specialist tools: {len(memory_specialist.tools)}")

        # Test a simple memory query
        team = RoundRobinGroupChat(
            [memory_specialist], termination_condition=MaxMessageTermination(max_messages=3)
        )

        task = "What active work items do we have in the system?"
        print(f"📝 Testing task: {task}")

        await Console(team.run_stream(task=task))

        return True

    except Exception as e:
        print(f"❌ Direct memory access failed: {e}")
        return False


async def main():
    """Test direct Cogni memory access"""
    print("🚀 Testing Direct Cogni Memory Access")

    success = await test_direct_memory_access()

    if success:
        print("✅ SUCCESS: Direct memory access working")
        print("🎯 This confirms Cogni memory system is functional")
        print("💡 We can build AutoGen integration on this foundation")
    else:
        print("❌ FAILED: Direct memory access not working")
        print("🔍 Need to fix memory system setup first")


if __name__ == "__main__":
    asyncio.run(main())
