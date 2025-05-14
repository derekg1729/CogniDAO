#!/usr/bin/env python
"""
Script to test the AddValidationReportTool with our newly created task.
"""

import sys

from infra_core.memory_system.tools.agent_facing.add_validation_report_tool import (
    ValidationResultInput,
    AddValidationReportInput,
    add_validation_report,
)
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank


def main():
    # The block_id from our previous task creation
    task_id = "0bfd2ed2-71ac-498f-847b-231c98e635c1"

    # Initialize memory bank with correct paths
    memory_bank = StructuredMemoryBank(
        dolt_db_path="./data/memory_dolt",
        chroma_path="./data/memory_chroma",
        chroma_collection="cogni",
    )

    # Create validation results - we'll mark two as pass and two as fail
    validation_input = AddValidationReportInput(
        block_id=task_id,
        results=[
            ValidationResultInput(
                criterion="All ProjectMetadata fields are mapped correctly",
                status="pass",
                notes="Verified all fields map to ProjectMetadata schema",
            ),
            ValidationResultInput(
                criterion="Input model validation works correctly",
                status="pass",
                notes="Tested with valid and invalid inputs",
            ),
            ValidationResultInput(
                criterion="Error handling for edge cases is implemented",
                status="fail",
                notes="Missing handling for null project owner",
            ),
            ValidationResultInput(
                criterion="Unit tests provide complete coverage",
                status="fail",
                notes="Only 80% test coverage achieved",
            ),
        ],
        validated_by="validator_agent",
        # Since we have failing criteria, this shouldn't mark as done
        mark_as_done=True,
    )

    # Call the tool function
    print(f"Adding validation report to task {task_id}...")
    result = add_validation_report(validation_input, memory_bank)

    # Display results
    if result.success:
        print("✓ Success! Validation report added")
        print(f"  Status updated: {result.status_updated}")
        print(f"  Validation summary: {result.validation_summary}")
        return 0
    else:
        print(f"✗ Failed to add validation report: {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
