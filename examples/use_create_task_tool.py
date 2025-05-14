#!/usr/bin/env python
"""
Script to test the CreateTaskMemoryBlockTool with data from an existing task.
"""

import sys

from infra_core.memory_system.tools.agent_facing.create_task_memory_block_tool import (
    CreateTaskMemoryBlockInput,
    create_task_memory_block,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


def main():
    # Initialize memory bank with correct paths
    memory_bank = StructuredMemoryBank(
        dolt_db_path="./data/memory_dolt",
        chroma_path="./data/memory_chroma",
        chroma_collection="cogni",
    )

    # Create task input based on project management schema task
    task_input = CreateTaskMemoryBlockInput(
        title="Implement CreateProjectMemoryBlockTool",
        description="Create an agent-facing tool for project creation with ExecutableMetadata fields to support the project management schema.",
        status="backlog",
        priority="P1",
        assignee="cogni_agent",
        # Planning fields
        action_items=[
            "Create input model based on ProjectMetadata schema",
            "Implement metadata mapping function",
            "Add validation for project-specific fields",
            "Create tests similar to CreateTaskMemoryBlockTool",
        ],
        acceptance_criteria=[
            "All ProjectMetadata fields are mapped correctly",
            "Input model validation works correctly",
            "Error handling for edge cases is implemented",
            "Unit tests provide complete coverage",
        ],
        expected_artifacts=[
            "create_project_memory_block_tool.py",
            "test_create_project_memory_block_tool.py",
        ],
        # Additional fields
        labels=["project-management", "agent-tool"],
        tool_hints=["code_editor", "git"],
        role_hint="developer",
        story_points=3.0,
        estimate_hours=4.0,
        # Agent framework compatibility
        execution_timeout_minutes=60,
        cost_budget_usd=2.0,
        # Creation metadata
        created_by="test_script",
        source_file="task-support-project-management-schemas.json",
        tags=["memory-system", "tools", "project-management"],
    )

    # Call the tool function
    print("Creating task memory block...")
    result = create_task_memory_block(task_input, memory_bank)

    # Display results
    if result.success:
        print(f"✓ Success! Task created with ID: {result.id}")
        print(f"  Created at: {result.timestamp}")
        return 0
    else:
        print(f"✗ Failed to create task: {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
