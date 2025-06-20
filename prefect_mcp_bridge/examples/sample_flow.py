"""
Sample Prefect flow using the MCP Bridge Package

This flow demonstrates how to use prefect-mcp-bridge to trigger
Dolt operations without shell scripts.
"""

from datetime import datetime
from prefect import flow, task
from prefect_mcp_bridge import dolt_add_task, dolt_commit_task, dolt_push_task
from prefect_mcp_bridge.utils import setup_mcp_environment, validate_mcp_connection


@task(name="setup_environment")
def setup_environment_task():
    """Setup and validate MCP environment"""
    print("🔧 Setting up MCP environment...")
    config = setup_mcp_environment()

    print("🔍 Validating MCP connection...")
    connection_status = validate_mcp_connection()

    if not connection_status["connected"]:
        raise Exception(f"MCP connection failed: {connection_status['error']}")

    print("✅ MCP environment ready!")
    return config


@task(name="create_test_data")
def create_test_data_task():
    """Simulate creating some test data that would be committed"""
    print("📝 Creating test data...")

    # In a real scenario, this might be:
    # - Running data pipeline that updates database
    # - Processing files that change memory blocks
    # - Any operation that modifies Dolt-tracked data

    test_data = {
        "timestamp": datetime.now().isoformat(),
        "operation": "sample_flow_execution",
        "description": "Test data created by sample flow",
    }

    print(f"✅ Test data created: {test_data}")
    return test_data


@flow(name="sample_mcp_bridge_flow", log_prints=True)
def sample_mcp_bridge_flow():
    """
    Sample flow demonstrating prefect-mcp-bridge usage

    This flow:
    1. Sets up the MCP environment
    2. Creates some test data (simulated)
    3. Uses MCP bridge tasks to: add -> commit -> push
    """
    print("🚀 Starting Sample MCP Bridge Flow")

    # Setup environment and validate connection
    setup_environment_task()

    # Create test data (simulated work that changes tracked data)
    test_data = create_test_data_task()

    print("🔄 Starting Dolt operations via MCP...")

    # Stage changes
    print("1️⃣ Adding changes...")
    add_result = dolt_add_task()
    print(f"   Add result: {add_result.get('message', 'Success')}")

    # Commit changes
    print("2️⃣ Committing changes...")
    commit_message = f"Sample flow execution - {test_data['timestamp']}"
    commit_result = dolt_commit_task(message=commit_message, author="prefect-mcp-bridge-sample")
    print(f"   Commit result: {commit_result.get('commit_hash', 'No hash')}")

    # Push changes
    print("3️⃣ Pushing changes...")
    push_result = dolt_push_task()
    print(f"   Push result: {push_result.get('message', 'Success')}")

    print("🎉 Sample MCP Bridge Flow completed successfully!")

    return {
        "test_data": test_data,
        "dolt_operations": {"add": add_result, "commit": commit_result, "push": push_result},
        "flow_status": "completed",
    }


@flow(name="sample_combined_workflow_flow")
def sample_combined_workflow_flow():
    """
    Sample flow using the convenience combined task

    This demonstrates the dolt_add_commit_push_task which
    performs all three operations in sequence.
    """
    print("🚀 Starting Combined Workflow Flow")

    # Setup
    setup_environment_task()
    test_data = create_test_data_task()

    print("🔄 Running combined add-commit-push operation...")

    # Single task that does add -> commit -> push
    from prefect_mcp_bridge.dolt import dolt_add_commit_push_task

    result = dolt_add_commit_push_task(
        message=f"Combined workflow - {test_data['timestamp']}",
        author="prefect-mcp-bridge-combined",
        branch="main",  # optional: specify branch
    )

    if result["success"]:
        print("✅ Combined workflow completed successfully!")
        print(f"   Commit hash: {result['commit'].get('commit_hash', 'N/A')}")
    else:
        print(f"❌ Combined workflow failed: {result['error']}")
        raise Exception(f"Workflow failed: {result['error']}")

    return result


if __name__ == "__main__":
    print("Running sample flows...")

    # Option 1: Individual tasks
    print("\n" + "=" * 50)
    print("RUNNING: Individual Tasks Flow")
    print("=" * 50)
    result1 = sample_mcp_bridge_flow()
    print(f"Result: {result1}")

    # Option 2: Combined task
    print("\n" + "=" * 50)
    print("RUNNING: Combined Workflow Flow")
    print("=" * 50)
    result2 = sample_combined_workflow_flow()
    print(f"Result: {result2}")

    print("\n🎉 All sample flows completed!")
