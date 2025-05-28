#!/usr/bin/env python
"""
Script to test the CreateWorkItem tool with data from the CogniCodeIndexingSystem-POC project.
"""

import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
    CreateWorkItemInput,
    create_work_item,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


def main():
    # Initialize memory bank with correct paths
    memory_bank = StructuredMemoryBank(
        dolt_db_path="./data/memory_dolt",
        chroma_path="./data/memory_chroma",
        chroma_collection="cogni",
    )

    # Define the implementation flow phases from the JSON file
    implementation_flow = [
        "📘 Phase 1: Selective CodeBlocks",
        "🧠 Phase 2: Auto-Extracted Code Graph",
        "🕸️ Phase 3: Link Code ↔ Memory",
        "🌍 Phase 4: Emergent OS Behaviors",
    ]

    # Success criteria from the JSON file
    success_criteria = [
        "Index core code functions as CodeBlocks into CogniMemory graph.",
        "Retrieve relevant CodeBlocks from LlamaIndex using natural language queries.",
        "Link CodeBlocks to related MemoryBlocks via tags and graph relationships.",
        "Show that agents can reason across both code and knowledge graphs.",
        "Generate agent proposals to update CodeBlocks, reviewed like memory proposals.",
        "Enable GitCogni to query indexed CodeBlocks to contextually review pull requests.",
    ]

    # Create project input based on the POC project JSON
    project_input = CreateWorkItemInput(
        type="project",
        title="CogniCodeIndexingSystem-POC",
        description="Proof-of-concept for parsing and semantically indexing AI system code into CodeBlocks within the CogniMemory graph. CodeBlocks will be linked to MemoryBlocks and governed by the same primitives as memory: versioned commits, semantic links, agent reflection, and DAO approval.",
        owner="cogni_agent",
        status="backlog",
        priority="P1",
        # Time tracking - use current date as start_date
        start_date=datetime.now(),
        # Planning fields
        acceptance_criteria=success_criteria,
        # Additional fields for project
        labels=["code-indexing", "memory-system", "proof-of-concept"],
        phase="Planning",
        implementation_flow=implementation_flow,
        # Agent framework compatibility
        tool_hints=["code_editor", "git", "llama_index"],
        role_hint="developer",
        execution_timeout_minutes=120,
        cost_budget_usd=5.0,
        # Creation metadata
        created_by="test_script",
        source_file="experiments/docs/roadmap/project-CogniCodeIndexingSystem-POC.json",
    )

    # Call the tool function
    print("Creating project...")
    result = create_work_item(project_input, memory_bank)

    # Display results
    if result.success:
        print(f"✓ Success! Project created with ID: {result.id}")
        print(f"  Created at: {result.timestamp}")
        return 0
    else:
        print(f"✗ Failed to create project: {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
