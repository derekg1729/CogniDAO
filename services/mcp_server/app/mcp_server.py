import os
import sys
import logging
from pathlib import Path
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.sql_link_manager import SQLLinkManager
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool,
    GetMemoryBlockInput,
    GetMemoryBlockOutput,
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
from infra_core.memory_system.pm_executable_links import ExecutableLinkManager
from infra_core.memory_system.tools.agent_facing.create_block_link_tool import (
    create_block_link_agent,
    CreateBlockLinkAgentInput,
)
from infra_core.memory_system.tools.agent_facing.get_memory_links_tool import (
    get_memory_links_tool,
    GetMemoryLinksInput,
    GetMemoryLinksOutput,
)

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

    # Initialize LinkManager components with SQL backend
    link_manager = SQLLinkManager(COGNI_DOLT_DIR)
    pm_links = ExecutableLinkManager(link_manager)

    # Attach link_manager to memory_bank for tool access
    memory_bank.link_manager = link_manager

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
    """Get memory blocks by ID(s) or filter by type/tags/metadata

    Block Retrieval by ID(s):
        block_ids: List of IDs of the memory blocks to retrieve (even single ID as list)

    Filtered Block Retrieval (specify at least one):
        type_filter: Filter by block type (knowledge, task, project, doc, interaction, bug, epic)
        tag_filters: List of tags to filter by (all must match)
        metadata_filters: Metadata key-value pairs to filter by (exact matches)
        limit: Maximum number of results to return (1-100)

    Output always contains 'blocks' array (0 to N blocks), even for single ID lookup.
    Cannot specify both block_ids and filtering parameters.
    """
    try:
        # Parse dict input into Pydantic model
        input_data = GetMemoryBlockInput(**input)

        # Execute the tool function
        result = get_memory_block_tool(
            memory_bank=memory_bank, **input_data.model_dump(exclude_none=True)
        )

        # Return the complete result
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in GetMemoryBlock MCP tool: {e}")
        return GetMemoryBlockOutput(
            success=False,
            blocks=[],
            error=f"Error retrieving memory blocks: {str(e)}",
            timestamp=datetime.now(),
        ).model_dump(mode="json")


# Register the GetMemoryLinks tool
@mcp.tool("GetMemoryLinks")
async def get_memory_links(input):
    """Get memory links with optional filtering by relation type

    Link Retrieval with Filtering:
        relation_filter: Optional filter by relation type (e.g., 'depends_on', 'subtask_of')
        limit: Maximum number of results to return (default: 100, max: 1000)
        cursor: Optional pagination cursor for retrieving next batch

    Output always contains 'links' array (0 to N links).
    """
    try:
        # Parse dict input into Pydantic model
        input_data = GetMemoryLinksInput(**input)

        # Execute the tool function
        result = get_memory_links_tool(
            memory_bank=memory_bank, **input_data.model_dump(exclude_none=True)
        )

        # Return the complete result
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in GetMemoryLinks MCP tool: {e}")
        return GetMemoryLinksOutput(
            success=False,
            links=[],
            error=f"Error retrieving memory links: {str(e)}",
            timestamp=datetime.now(),
        ).model_dump(mode="json")


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


# Register the CreateBlockLink tool
@mcp.tool("CreateBlockLink")
async def create_block_link(input):
    """Create a link between memory blocks, enabling task dependencies, parent-child relationships, and other connections

    Args:
        source_block_id: ID of the source block (the 'from' block)
        target_block_id: ID of the target block (the 'to' block)
        relation: Type of relationship between blocks (e.g., 'depends_on', 'is_blocked_by', 'child_of')
        bidirectional: Whether to create the inverse relationship automatically (default: False)
        priority: Priority of the link (higher numbers = more important, default: 0)
        metadata: Additional metadata about the link (optional)
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = CreateBlockLinkAgentInput(**input)

        # Call the agent-facing tool function
        result = await create_block_link_agent(
            source_block_id=parsed_input.source_block_id,
            target_block_id=parsed_input.target_block_id,
            relation=parsed_input.relation,
            bidirectional=parsed_input.bidirectional,
            priority=parsed_input.priority,
            metadata=parsed_input.metadata,
            memory_bank=memory_bank,
        )

        # Return result in appropriate format for MCP
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error creating block link: {e}")
        return {"success": False, "message": "Failed to create block link", "error_details": str(e)}


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
