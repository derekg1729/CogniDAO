import os
import sys
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool,
    GetMemoryBlockInput,
)
from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
    create_work_item_tool,
    CreateWorkItemInput,
)
from infra_core.memory_system.tools.agent_facing.update_memory_block_tool import (
    update_memory_block_tool,
    UpdateMemoryBlockToolInput,
)
from infra_core.memory_system.tools.agent_facing.update_work_item_tool import (
    update_work_item_tool,
    UpdateWorkItemInput,
)
from infra_core.memory_system.link_manager import InMemoryLinkManager
from infra_core.memory_system.pm_executable_links import ExecutableLinkManager

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,  # Use stdout for unified JSON-friendly output
)

logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))


# Initialize StructuredMemoryBank using environment variable
COGNI_DOLT_DIR = "/Users/derek/dev/cogni/data/memory_dolt"
CHROMA_PATH = "/Users/derek/dev/cogni/data/memory_chroma"
CHROMA_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", "cogni_mcp_collection")

# # Ensure directories exist
# os.makedirs(COGNI_DOLT_DIR, exist_ok=True)
# os.makedirs(CHROMA_PATH, exist_ok=True)

try:
    # Initialize memory bank
    memory_bank = StructuredMemoryBank(
        dolt_db_path=COGNI_DOLT_DIR,
        chroma_path=CHROMA_PATH,
        chroma_collection=CHROMA_COLLECTION_NAME,
    )

    # Initialize LinkManager components
    link_manager = InMemoryLinkManager()
    pm_links = ExecutableLinkManager(link_manager)

except Exception as e:
    logger.error(f"Failed to initialize StructuredMemoryBank: {e}")
    logger.error("Please run init_dolt_schema.py to initialize the Dolt database")
    sys.exit(1)

# Create a FastMCP server instance with a specific name
mcp = FastMCP("cogni-memory")


# Register the CreateWorkItem tool
@mcp.tool("CreateWorkItem")
async def create_work_item(input):
    """Create a new work item (project, epic, task, or bug)

    Args:
        type: Type of work item to create (project, epic, task, or bug)
        title: Title of the work item
        description: Description of the work item
        owner: Owner or assignee of the work item
        acceptance_criteria: List of acceptance criteria for the work item
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = CreateWorkItemInput(**input)
        result = create_work_item_tool(parsed_input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error creating work item: {e}")
        return {"error": str(e)}


# Register the GetMemoryBlock tool
@mcp.tool("GetMemoryBlock")
async def get_memory_block(input):
    """Get a memory block by ID

    Args:
        block_id: ID of the memory block to retrieve
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = GetMemoryBlockInput(**input)
        result = get_memory_block_tool(parsed_input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error getting memory block: {e}")
        return {"error": str(e)}


# Register the UpdateMemoryBlock tool
@mcp.tool("UpdateMemoryBlock")
async def update_memory_block(input):
    """Update an existing memory block

    Args:
        block_id: ID of the memory block to update
        text: Updated text content
        state: Updated state (draft, published, archived)
        visibility: Updated visibility (internal, public, restricted)
        tags: Updated tags
        metadata: Updated metadata
        links: Updated block links
        merge_tags: Whether to merge or replace tags
        merge_metadata: Whether to merge or replace metadata
        merge_links: Whether to merge or replace links
        author: Who is making the update
        agent_id: Agent identifier
        change_note: Note explaining the update
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = UpdateMemoryBlockToolInput(**input)
        result = update_memory_block_tool(parsed_input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error updating memory block: {e}")
        return {"error": str(e)}


# Register the UpdateWorkItem tool
@mcp.tool("UpdateWorkItem")
async def update_work_item(input):
    """Update an existing work item (project, epic, task, or bug)

    Args:
        block_id: ID of the work item to update
        title: Updated title of the work item
        description: Updated description of the work item
        status: Updated status of the work item
        priority: Updated priority level
        owner: Updated owner or assignee
        acceptance_criteria: Updated criteria for completion
        action_items: Updated action items
        expected_artifacts: Updated expected deliverables
        story_points: Updated story points
        estimate_hours: Updated time estimate
        tags: Updated tags
        labels: Updated labels
        execution_phase: Updated execution phase (only for in_progress status)
        state: Updated state of the block
        visibility: Updated visibility level
        merge_tags: Whether to merge or replace tags
        merge_metadata: Whether to merge or replace metadata
        author: Who is making the update
        agent_id: Agent identifier
        change_note: Note explaining the update
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = UpdateWorkItemInput(**input)
        result = update_work_item_tool(parsed_input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error updating work item: {e}")
        return {"error": str(e)}


class HealthCheckOutput:
    """Simple health check output."""

    def __init__(self, healthy: bool, memory_bank_status: str, link_manager_status: str):
        self.healthy = healthy
        self.memory_bank_status = memory_bank_status
        self.link_manager_status = link_manager_status


# Register a health check tool
@mcp.tool("HealthCheck")
async def health_check():
    """Check if the memory bank is initialized"""
    memory_bank_ok = memory_bank is not None
    link_manager_ok = link_manager is not None and pm_links is not None

    return HealthCheckOutput(
        healthy=memory_bank_ok and link_manager_ok,
        memory_bank_status="initialized" if memory_bank_ok else "not_initialized",
        link_manager_status="initialized" if link_manager_ok else "not_initialized",
    )


# initial JSON for local MCP server:
#  "cogni-mcp": {
#       "command": "uv --directory /Users/derek/dev/cogni/services/mcp_server run app/mcp_server.py",
#       "env": {
#         "CHROMA_COLLECTION_NAME": "cogni_mcp_collection"
#       }
#     }


# When this file is executed directly, use the MCP CLI
if __name__ == "__main__":
    mcp.run()
