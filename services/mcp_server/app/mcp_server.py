import os
import sys
import logging
import importlib.util
from pathlib import Path
from datetime import datetime
import json

from mcp.server.fastmcp import FastMCP
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.sql_link_manager import SQLLinkManager
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool,
    GetMemoryBlockInput,
    GetMemoryBlockOutput,
)
from infra_core.memory_system.tools.agent_facing.get_active_work_items_tool import (
    get_active_work_items_tool,
    GetActiveWorkItemsInput,
    GetActiveWorkItemsOutput,
)
from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
    create_work_item_tool,
    CreateWorkItemInput,
)
from infra_core.memory_system.tools.agent_facing.create_memory_block_agent_tool import (
    create_memory_block_agent_tool,
    CreateMemoryBlockAgentInput,
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
from infra_core.memory_system.tools.agent_facing.get_linked_blocks_tool import (
    get_linked_blocks_tool,
    GetLinkedBlocksInput,
    GetLinkedBlocksOutput,
)
from infra_core.memory_system.tools.agent_facing.delete_memory_block_tool import (
    delete_memory_block_tool,
    DeleteMemoryBlockToolInput,
)
from infra_core.memory_system.tools.memory_core.query_memory_blocks_tool import (
    query_memory_blocks_core,
    QueryMemoryBlocksInput,
    QueryMemoryBlocksOutput,
)
from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
    dolt_repo_tool,
    DoltCommitInput,
    DoltCommitOutput,
    dolt_status_tool,
    DoltStatusInput,
    DoltStatusOutput,
    dolt_pull_tool,
    DoltPullInput,
    dolt_branch_tool,
    DoltBranchInput,
)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,  # Use stdout for unified JSON-friendly output
)

logger = logging.getLogger(__name__)

# Validate critical dependencies are available

if importlib.util.find_spec("llama_index.embeddings.huggingface") is None:
    logger.error("Critical dependency missing - llama_index.embeddings.huggingface")
    sys.exit(1)


# Add project root to Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

# Initialize StructuredMemoryBank using environment variables
CHROMA_PATH = os.environ.get("CHROMA_PATH", "/tmp/cogni_chroma")  # Make configurable
CHROMA_COLLECTION_NAME = os.environ.get("CHROMA_COLLECTION_NAME", "cogni_mcp_collection")

# Ensure directories exist
os.makedirs(CHROMA_PATH, exist_ok=True)

try:
    # Initialize MySQL connection config for remote Dolt SQL server
    dolt_config = DoltConnectionConfig(
        host=os.environ.get("DOLT_HOST", "localhost"),
        port=int(os.environ.get("DOLT_PORT", "3306")),
        user=os.environ.get("DOLT_USER", "root"),
        password=os.environ.get("DOLT_ROOT_PASSWORD", ""),
        database=os.environ.get(
            "DOLT_DATABASE", "cogni-dao-memory"
        ),  # Fixed default to match production
    )

    # Test database connection before proceeding
    logger.info(f"Testing database connection to {dolt_config.host}:{dolt_config.port}")
    try:
        import mysql.connector

        test_conn = mysql.connector.connect(
            host=dolt_config.host,
            port=dolt_config.port,
            user=dolt_config.user,
            password=dolt_config.password,
            database=dolt_config.database,
            connect_timeout=5,
        )
        cursor = test_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        test_conn.close()
        logger.info("✅ Database connection successful")
    except Exception as db_error:
        logger.error(f"❌ Database connection failed: {db_error}")
        logger.error(
            f"Config: host={dolt_config.host}, port={dolt_config.port}, user={dolt_config.user}, database={dolt_config.database}"
        )
        raise

    # Initialize memory bank
    memory_bank = StructuredMemoryBank(
        chroma_path=CHROMA_PATH,
        chroma_collection=CHROMA_COLLECTION_NAME,
        dolt_connection_config=dolt_config,
    )

    # Initialize LinkManager components with SQL backend using same config
    link_manager = SQLLinkManager(dolt_config)
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


# Register the GetActiveWorkItems tool
@mcp.tool("GetActiveWorkItems")
async def get_active_work_items(input):
    """Get work items that are currently active (status='in_progress') with optional filtering

    Args:
        priority_filter: Optional filter by priority level (P0 highest, P5 lowest)
        work_item_type_filter: Optional filter by work item type (task, project, epic, bug)
        limit: Maximum number of results to return (1-100)

    Output contains 'work_items' array sorted by priority (P0 first) then creation date.
    """
    try:
        # Parse dict input into Pydantic model
        input_data = GetActiveWorkItemsInput(**input)

        # Execute the tool function
        result = get_active_work_items_tool(
            memory_bank=memory_bank, **input_data.model_dump(exclude_none=True)
        )

        # Return the complete result
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in GetActiveWorkItems MCP tool: {e}")
        return GetActiveWorkItemsOutput(
            success=False,
            work_items=[],
            error=f"Error retrieving active work items: {str(e)}",
            timestamp=datetime.now(),
        ).model_dump(mode="json")


# Register the QueryMemoryBlocksSemantic tool
@mcp.tool("QueryMemoryBlocksSemantic")
async def query_memory_blocks_semantic(input):
    """Query memory blocks using semantic search with chroma vector database

    Semantic Search with Filters:
        query_text: Text to search for semantically (required)
        type_filter: Optional filter by block type (knowledge, task, project, doc, interaction, bug, epic)
        tag_filters: Optional list of tags to filter by (all must match)
        metadata_filters: Optional metadata key-value pairs to filter by (exact matches)
        top_k: Maximum number of results to return (1-20, default: 5)

    Output contains 'blocks' array of semantically relevant memory blocks.
    """
    try:
        # Parse dict input into Pydantic model
        input_data = QueryMemoryBlocksInput(**input)

        # Execute the core query function
        result = query_memory_blocks_core(input_data, memory_bank)

        # Return the complete result
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in QueryMemoryBlocksSemantic MCP tool: {e}")
        return QueryMemoryBlocksOutput(
            success=False,
            blocks=[],
            error=f"Error performing semantic search: {str(e)}",
            timestamp=datetime.now(),
        ).model_dump(mode="json")


# Register the GetLinkedBlocks tool
@mcp.tool("GetLinkedBlocks")
async def get_linked_blocks(input):
    """Get all blocks linked to a specific block with relationship information

    Args:
        source_block_id: ID of the source block to find links for
        relation_filter: Optional filter by specific relation type (e.g., 'subtask_of', 'depends_on')
        direction_filter: Filter by link direction relative to source block (incoming, outgoing, both)
        limit: Maximum number of linked blocks to return (1-200)

    Output contains 'linked_blocks' array with full block details and relationship context.
    """
    try:
        # Parse dict input into Pydantic model
        input_data = GetLinkedBlocksInput(**input)

        # Execute the tool function
        result = get_linked_blocks_tool(
            memory_bank=memory_bank, **input_data.model_dump(exclude_none=True)
        )

        # Return the complete result
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in GetLinkedBlocks MCP tool: {e}")
        return GetLinkedBlocksOutput(
            success=False,
            source_block_id=input.get("source_block_id", "unknown"),
            linked_blocks=[],
            total_count=0,
            error=f"Error retrieving linked blocks: {str(e)}",
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


# Register the DeleteMemoryBlock tool
@mcp.tool("DeleteMemoryBlock")
async def delete_memory_block(input):
    """Delete an existing memory block with dependency validation

    Args:
        block_id: ID of the memory block to delete
        validate_dependencies: If True, check for dependent blocks and fail if any exist
        author: Who is performing the deletion
        agent_id: Agent identifier for tracking
        change_note: Optional note explaining the reason for deletion
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = DeleteMemoryBlockToolInput(**input)
        result = delete_memory_block_tool(parsed_input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error deleting memory block: {e}")
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


# Register the CreateMemoryBlock tool
@mcp.tool("CreateMemoryBlock")
async def create_memory_block(input):
    """Create a new general memory block (doc, knowledge, or log)

    Args:
        type: Type of memory block to create (doc, knowledge, or log)
        title: Title of the memory block
        content: Primary content/text of the memory block
        audience: Intended audience (doc type only)
        section: Section or category (doc type only)
        source: Source of the knowledge (knowledge type only)
        validity: Validity status (knowledge type only)
        input_text: Input text from interaction (log type only)
        output_text: Output text from interaction (log type only)
        tags: Tags for categorizing this memory block
        state: Initial state of the block
        visibility: Visibility level of the block
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = CreateMemoryBlockAgentInput(**input)
        result = create_memory_block_agent_tool(parsed_input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error creating memory block: {e}")
        return {"error": str(e)}


# Register the DoltCommit tool
@mcp.tool("DoltCommit")
async def dolt_commit(input):
    """Commit working changes to Dolt using the memory bank's writer

    Args:
        commit_message: Commit message for the Dolt changes (required, 1-500 chars)
        tables: Optional list of specific tables to add/commit. If not provided, all standard tables will be committed
        author: Optional author attribution for the commit (max 100 chars)

    Returns:
        success: Whether the commit operation succeeded
        commit_hash: The Dolt commit hash if successful
        message: Human-readable result message
        tables_committed: List of tables that were committed
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = DoltCommitInput(**input)
        result = dolt_repo_tool(parsed_input, memory_bank=memory_bank)
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltCommit MCP tool: {e}")
        return DoltCommitOutput(
            success=False,
            message=f"Commit failed: {str(e)}",
            error=f"Error during dolt_commit: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltPush tool
@mcp.tool("DoltPush")
async def mcp_dolt_push(
    remote_name: str = "origin",
    branch: str = "main",
    force: bool = False,
) -> str:
    """
    Push changes to a remote repository using Dolt.

    Args:
        remote_name: Name of the remote to push to (default: 'origin')
        branch: Branch to push (default: 'main')
        force: Whether to force push, overriding safety checks

    Returns:
        JSON string with push results including success status and message
    """
    try:
        # Import the dolt_push_tool function and input model
        from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
            DoltPushInput,
            dolt_push_tool,
        )

        # Create input object
        input_data = DoltPushInput(
            remote_name=remote_name,
            branch=branch,
            force=force,
        )

        # Execute the push operation
        result = dolt_push_tool(input_data, memory_bank)

        # Return JSON representation
        return result.model_dump_json(indent=2)

    except Exception as e:
        logger.error(f"Error in DoltPush tool: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# Register the DoltStatus tool
@mcp.tool("DoltStatus")
async def dolt_status(input):
    """Get repository status using Dolt system tables

    Returns:
        current_branch: Current active branch
        is_clean: True if working tree is clean
        staged_tables: Tables with staged changes
        unstaged_tables: Tables with unstaged changes
        untracked_tables: New untracked tables
        total_changes: Total number of changes
        ahead: Commits ahead of remote
        behind: Commits behind remote
        conflicts: Tables with conflicts
        message: Human-readable status summary
        timestamp: Timestamp of operation
    """
    logger.info("DoltStatus MCP tool called")

    try:
        # Parse dict input into Pydantic model
        parsed_input = DoltStatusInput(**input)
        result = dolt_status_tool(parsed_input, memory_bank=memory_bank)
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in DoltStatus MCP tool: {e}")
        return DoltStatusOutput(
            success=False,
            current_branch="unknown",
            is_clean=False,
            total_changes=0,
            message=f"Status check failed: {str(e)}",
            error=str(e),
        ).model_dump(mode="json")


# Register the DoltPull tool
@mcp.tool("DoltPull")
async def mcp_dolt_pull(
    remote_name: str = "origin",
    branch: str = None,
    force: bool = False,
    no_ff: bool = False,
    squash: bool = False,
) -> str:
    """
    Pull changes from a remote repository using Dolt.

    Args:
        remote_name: Name of the remote to pull from (default: 'origin')
        branch: Specific branch to pull (optional)
        force: Whether to force pull, ignoring conflicts
        no_ff: Create a merge commit even for fast-forward merges
        squash: Merge changes to working set without updating commit history

    Returns:
        JSON string with pull results including success status and message
    """
    try:
        # Create input object
        input_data = DoltPullInput(
            remote_name=remote_name,
            branch=branch,
            force=force,
            no_ff=no_ff,
            squash=squash,
        )

        # Execute the pull operation
        result = dolt_pull_tool(input_data, memory_bank)

        # Return JSON representation
        return result.model_dump_json(indent=2)

    except Exception as e:
        logger.error(f"Error in DoltPull tool: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool("DoltBranch")
async def mcp_dolt_branch(
    branch_name: str,
    start_point: str = None,
    force: bool = False,
) -> str:
    """
    Create a new branch using Dolt.

    Args:
        branch_name: Name of the new branch to create
        start_point: Commit, branch, or tag to start the branch from (optional)
        force: Whether to force creation, overriding safety checks

    Returns:
        JSON string with branch creation results including success status and message
    """
    try:
        # Create input object
        input_data = DoltBranchInput(
            branch_name=branch_name,
            start_point=start_point,
            force=force,
        )

        # Execute the branch creation operation
        result = dolt_branch_tool(input_data, memory_bank)

        # Return JSON representation
        return result.model_dump_json(indent=2)

    except Exception as e:
        logger.error(f"Error in DoltBranch tool: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# Register the DoltListBranches tool
@mcp.tool("DoltListBranches")
async def dolt_list_branches(input):
    """List all Dolt branches with their information

    Returns:
        success: Whether the operation succeeded
        branches: List of branch information objects
        current_branch: Currently active branch
        message: Human-readable result message
        timestamp: Timestamp of operation
    """
    try:
        # Import the function locally for now
        from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
            DoltListBranchesInput,
            DoltListBranchesOutput,
            dolt_list_branches_tool,
        )

        # Parse dict input into Pydantic model
        parsed_input = DoltListBranchesInput(**input)
        result = dolt_list_branches_tool(parsed_input, memory_bank=memory_bank)
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in DoltListBranches MCP tool: {e}")
        # Import locally for error handling too
        from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
            DoltListBranchesOutput,
        )

        return DoltListBranchesOutput(
            success=False,
            branches=[],
            current_branch="unknown",
            message=f"Failed to list branches: {str(e)}",
            error=f"Error during branch listing: {str(e)}",
        ).model_dump(mode="json")


# Register a health check tool
@mcp.tool("HealthCheck")
async def health_check():
    """Check if the memory bank is initialized"""
    memory_bank_ok = memory_bank is not None
    link_manager_ok = link_manager is not None and pm_links is not None

    return {
        "healthy": memory_bank_ok and link_manager_ok,
        "memory_bank_status": "initialized" if memory_bank_ok else "not_initialized",
        "link_manager_status": "initialized" if link_manager_ok else "not_initialized",
        "timestamp": datetime.now().isoformat(),
    }


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
