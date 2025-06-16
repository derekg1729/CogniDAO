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
    CreateMemoryBlockAgentOutput,
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
    dolt_push_tool,
    DoltPushInput,
    dolt_status_tool,
    DoltStatusInput,
    DoltStatusOutput,
    dolt_pull_tool,
    DoltPullInput,
    dolt_branch_tool,
    DoltBranchInput,
    dolt_list_branches_tool,
    DoltListBranchesInput,
    dolt_add_tool,
    DoltAddInput,
    DoltAddOutput,
    dolt_checkout_tool,
    DoltCheckoutInput,
    DoltCheckoutOutput,
    dolt_diff_tool,
    DoltDiffInput,
    DoltDiffOutput,
    dolt_auto_commit_and_push_tool,
    DoltAutoCommitInput,
    DoltAutoCommitOutput,
    dolt_create_pull_request_tool,
    DoltCreatePullRequestInput,
    DoltCreatePullRequestOutput,
    dolt_merge_tool,
    DoltMergeInput,
    DoltMergeOutput,
    dolt_compare_branches_tool,
    DoltCompareBranchesInput,
    DoltCompareBranchesOutput,
    dolt_approve_pull_request_tool,
    DoltApprovePullRequestInput,
    DoltApprovePullRequestOutput,
    dolt_reset_tool,
    DoltResetInput,
    DoltResetOutput,
)
from infra_core.memory_system.tools.agent_facing.bulk_create_blocks_tool import (
    bulk_create_blocks,
    BulkCreateBlocksInput,
    BulkCreateBlocksOutput,
)
from infra_core.memory_system.tools.agent_facing.bulk_create_links_tool import (
    bulk_create_links,
    BulkCreateLinksInput,
    BulkCreateLinksOutput,
)
from infra_core.memory_system.tools.agent_facing.dolt_namespace_tool import (
    list_namespaces_tool,
    ListNamespacesInput,
    ListNamespacesOutput,
)
from infra_core.memory_system.tools.agent_facing.create_namespace_tool import (
    create_namespace_tool,
    CreateNamespaceInput,
    CreateNamespaceOutput,
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

# Global state for MCP server
_memory_bank = None
_link_manager = None
_pm_links = None
_current_branch = None
_current_namespace = None  # Add global namespace state


# Detect current Git branch or use environment variable
def get_current_branch() -> str:
    """
    Detect the current Git branch or use environment variable.
    Falls back to 'main' if detection fails.
    """
    # First check environment variable
    env_branch = os.environ.get("DOLT_BRANCH")
    if env_branch:
        logger.info(f"Using branch from DOLT_BRANCH environment variable: {env_branch}")
        return env_branch

    # STUBBED: Always return "main" for now to ensure consistent Dolt branch usage
    logger.info("STUBBED: Always returning 'main' branch (Git detection disabled)")
    return "main"

    # # Try to detect Git branch
    # try:
    #     import subprocess

    #     result = subprocess.run(
    #         ["git", "branch", "--show-current"],
    #         cwd=project_root,
    #         capture_output=True,
    #         text=True,
    #         timeout=5,
    #     )
    #     if result.returncode == 0 and result.stdout.strip():
    #         git_branch = result.stdout.strip()
    #         logger.info(f"Detected Git branch: {git_branch}")
    #         return git_branch
    # except Exception as e:
    #     logger.warning(f"Could not detect Git branch: {e}")

    # # Fallback to main
    # logger.info("Falling back to 'main' branch")
    # return "main"


def get_current_namespace() -> str:
    """
    Get the current namespace for MCP operations.

    This checks the DOLT_NAMESPACE environment variable first,
    then falls back to the default 'legacy' namespace.

    Returns:
        The namespace to use for all MCP operations
    """
    # First check environment variable
    env_namespace = os.environ.get("DOLT_NAMESPACE")
    logger.info("🔍 [NAMESPACE] Checking DOLT_NAMESPACE environment variable...")

    if env_namespace:
        logger.info(
            f"✅ [NAMESPACE] Using namespace from DOLT_NAMESPACE environment variable: '{env_namespace}'"
        )
        return env_namespace

    # Fallback to legacy namespace
    logger.info("📋 [NAMESPACE] DOLT_NAMESPACE not set, using default 'legacy' namespace")
    return "legacy"


def _initialize_memory_system():
    """
    Lazy initialization of the memory system components.
    This prevents database connections during module import for testing.
    """
    global _memory_bank, _link_manager, _pm_links, _current_branch, _current_namespace

    if _memory_bank is not None:
        return _memory_bank, _link_manager, _pm_links

    # Log environment variables for debugging
    logger.info("🔍 [ENV] MCP Server Environment Variables:")
    logger.info(f"    DOLT_NAMESPACE = '{os.environ.get('DOLT_NAMESPACE', '(not set)')}'")
    logger.info(f"    DOLT_BRANCH = '{os.environ.get('DOLT_BRANCH', '(not set)')}'")
    logger.info(f"    DOLT_HOST = '{os.environ.get('DOLT_HOST', '(not set)')}'")
    logger.info(f"    DOLT_DATABASE = '{os.environ.get('DOLT_DATABASE', '(not set)')}'")

    # Get the branch to use for Dolt operations
    _current_branch = get_current_branch()

    # Get the namespace to use for MCP operations
    logger.info("🚀 [NAMESPACE] Initializing namespace context...")
    _current_namespace = get_current_namespace()
    logger.info(f"🎯 [NAMESPACE] Global namespace context set to: '{_current_namespace}'")

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

        # Initialize memory bank with detected branch
        logger.info(f"Initializing StructuredMemoryBank with branch: {_current_branch}")
        _memory_bank = StructuredMemoryBank(
            chroma_path=CHROMA_PATH,
            chroma_collection=CHROMA_COLLECTION_NAME,
            dolt_connection_config=dolt_config,
            branch=_current_branch,
        )

        # 🔧 CRITICAL FIX: Enable persistent connections to maintain branch context
        # This ensures all MCP tool operations stay on the correct branch
        logger.info(f"Enabling persistent connections on branch: {_current_branch}")
        _memory_bank.use_persistent_connections(_current_branch)
        logger.info(
            f"✅ Persistent connections enabled - all operations will use branch: {_memory_bank.branch}"
        )

        # Initialize LinkManager components with SQL backend using same config
        _link_manager = SQLLinkManager(dolt_config)
        _pm_links = ExecutableLinkManager(_link_manager)

        # 🔧 CRITICAL FIX: Enable persistent connections on LinkManager too
        # This ensures link operations also maintain branch context
        logger.info(f"Enabling persistent connections on LinkManager for branch: {_current_branch}")
        _link_manager.use_persistent_connection(_current_branch)
        logger.info(
            f"✅ LinkManager persistent connections enabled on branch: {_link_manager.active_branch}"
        )

        # Attach link_manager to memory_bank for tool access
        _memory_bank.link_manager = _link_manager

    except Exception as e:
        logger.error(f"Failed to initialize StructuredMemoryBank: {e}")
        logger.error("Please run init_dolt_schema.py to initialize the Dolt database")
        raise RuntimeError(f"Memory system initialization failed: {e}")

    return _memory_bank, _link_manager, _pm_links


def get_memory_bank():
    """Get the initialized memory bank, initializing if necessary."""
    memory_bank, _, _ = _initialize_memory_system()
    return memory_bank


def get_link_manager():
    """Get the initialized link manager, initializing if necessary."""
    _, link_manager, _ = _initialize_memory_system()
    return link_manager


def get_pm_links():
    """Get the initialized PM links, initializing if necessary."""
    _, _, pm_links = _initialize_memory_system()
    return pm_links


def get_current_namespace_context() -> str:
    """
    Get the current namespace context for this MCP session.

    Returns the namespace that will be used for all MCP operations
    unless explicitly overridden in individual tool calls.

    Returns:
        The current namespace identifier
    """
    current_ns = _current_namespace or get_current_namespace()
    logger.info(f"📋 [NAMESPACE] Current namespace context: '{current_ns}'")
    return current_ns


def inject_current_namespace(input_data: dict) -> dict:
    """
    Inject the current namespace into tool input if not already specified.

    This ensures all MCP tools use the same namespace context unless explicitly overridden.

    Args:
        input_data: Input dictionary for MCP tool

    Returns:
        Input dictionary with namespace_id set to current namespace if not present
    """
    if "namespace_id" not in input_data or input_data["namespace_id"] is None:
        current_ns = _current_namespace or get_current_namespace()
        input_data["namespace_id"] = current_ns
        logger.info(
            f"🔧 [NAMESPACE] Injected current namespace: '{current_ns}' (no namespace specified in request)"
        )
    else:
        logger.info(
            f"🎯 [NAMESPACE] Using explicit namespace from request: '{input_data['namespace_id']}'"
        )
    return input_data


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
        namespace_id: Namespace ID for multi-tenant organization (defaults to current namespace)
        owner: Owner or assignee of the work item
        acceptance_criteria: List of acceptance criteria for the work item
    """
    try:
        # Inject current namespace if not specified
        input = inject_current_namespace(input)

        # Parse dict input into Pydantic model
        parsed_input = CreateWorkItemInput(**input)
        result = create_work_item_tool(parsed_input, memory_bank=get_memory_bank())
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
        namespace_id: Optional filter by namespace ID for multi-tenant operations (defaults to current namespace)
        tag_filters: List of tags to filter by (all must match)
        metadata_filters: Metadata key-value pairs to filter by (exact matches)
        limit: Maximum number of results to return (1-100)

    Output always contains 'blocks' array (0 to N blocks), even for single ID lookup.
    Cannot specify both block_ids and filtering parameters.
    """
    try:
        # Inject current namespace if not specified and not using block_ids
        if "block_ids" not in input or input["block_ids"] is None:
            input = inject_current_namespace(input)

        # Parse dict input into Pydantic model
        input_data = GetMemoryBlockInput(**input)

        # Execute the tool function
        result = get_memory_block_tool(
            memory_bank=get_memory_bank(), **input_data.model_dump(exclude_none=True)
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
            memory_bank=get_memory_bank(), **input_data.model_dump(exclude_none=True)
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
            memory_bank=get_memory_bank(), **input_data.model_dump(exclude_none=True)
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
        namespace_id: Optional filter by namespace ID for multi-tenant operations (defaults to current namespace)
        tag_filters: Optional list of tags to filter by (all must match)
        metadata_filters: Optional metadata key-value pairs to filter by (exact matches)
        top_k: Maximum number of results to return (1-20, default: 5)

    Output contains 'blocks' array of semantically relevant memory blocks.
    """
    try:
        # Inject current namespace if not specified
        input = inject_current_namespace(input)

        # Parse dict input into Pydantic model
        parsed_input = QueryMemoryBlocksInput(**input)
        result = query_memory_blocks_core(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in QueryMemoryBlocksSemantic MCP tool: {e}")
        return QueryMemoryBlocksOutput(
            success=False,
            blocks=[],
            message=f"Semantic query failed: {str(e)}",
            active_branch="unknown",
            error=f"Error during query_memory_blocks_semantic: {str(e)}",
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
            memory_bank=get_memory_bank(), **input_data.model_dump(exclude_none=True)
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
        result = update_memory_block_tool(parsed_input, memory_bank=get_memory_bank())
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
        result = delete_memory_block_tool(parsed_input, memory_bank=get_memory_bank())
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
        result = update_work_item_tool(parsed_input, memory_bank=get_memory_bank())
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
            memory_bank=get_memory_bank(),
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
        content: Primary content/text of the memory block
        namespace_id: Namespace ID for multi-tenant organization (defaults to current namespace)
        title: Title of the memory block
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
        # Inject current namespace if not specified
        input = inject_current_namespace(input)

        # Parse dict input into Pydantic model
        parsed_input = CreateMemoryBlockAgentInput(**input)
        result = create_memory_block_agent_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in CreateMemoryBlock MCP tool: {e}")
        return CreateMemoryBlockAgentOutput(
            success=False,
            block_type=input.get("type", "unknown"),
            active_branch=get_memory_bank().dolt_writer.active_branch,
            error=f"Error during create_memory_block: {str(e)}",
        ).model_dump(mode="json")


# Register the BulkCreateBlocks tool
@mcp.tool("BulkCreateBlocks")
async def bulk_create_blocks_mcp(input):
    """Create multiple memory blocks in a single operation with independent success tracking

    Args:
        blocks: List of block specifications to create (1-1000 blocks)
        stop_on_first_error: If True, stop processing on first error. If False, continue and report all results.
        default_x_agent_id: Default agent ID for blocks that don't specify one
        default_x_tool_id: Default tool ID for blocks that don't specify one
        default_x_session_id: Default session ID for grouping all blocks in this bulk operation

    Returns:
        success: Whether ALL blocks were created successfully (failed_count == 0)
        partial_success: Whether at least one block was created successfully
        total_blocks: Total number of blocks attempted
        successful_blocks: Number of blocks created successfully
        failed_blocks: Number of blocks that failed to create
        results: Individual results for each block
        active_branch: Current active branch
        timestamp: When the bulk operation completed
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = BulkCreateBlocksInput(**input)
        result = bulk_create_blocks(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in BulkCreateBlocks MCP tool: {e}")
        return BulkCreateBlocksOutput(
            success=False,
            partial_success=False,
            total_blocks=0,
            successful_blocks=0,
            failed_blocks=0,
            results=[],
            active_branch="unknown",
            timestamp=datetime.now(),
        ).model_dump(mode="json")


# Register the BulkCreateLinks tool
@mcp.tool("BulkCreateLinks")
async def bulk_create_links_mcp(input):
    """Create multiple memory block links in a single operation with independent success tracking

    Args:
        links: List of link specifications to create (1-5000 links)
        stop_on_first_error: If True, stop processing on first error. If False, continue and report all results.
        validate_blocks_exist: Whether to validate that referenced blocks exist before creating links

    Returns:
        success: Whether ALL links were created successfully (failed_count == 0)
        partial_success: Whether at least one link was created successfully
        total_specs: Total number of link specs attempted
        successful_specs: Number of link specs created successfully
        failed_specs: Number of link specs that failed to create
        skipped_specs: Number of link specs skipped due to early termination
        total_actual_links: Total number of actual links created (including bidirectional)
        results: Individual results for each link spec
        active_branch: Current active branch if available
        timestamp: When the bulk operation completed
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = BulkCreateLinksInput(**input)
        result = bulk_create_links(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in BulkCreateLinks MCP tool: {e}")
        return BulkCreateLinksOutput(
            success=False,
            partial_success=False,
            total_specs=0,
            successful_specs=0,
            failed_specs=0,
            skipped_specs=0,
            total_actual_links=0,
            results=[],
            active_branch=None,
            timestamp=datetime.now(),
        ).model_dump(mode="json")


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
        result = dolt_repo_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltCommit MCP tool: {e}")
        return DoltCommitOutput(
            success=False,
            message=f"Commit failed: {str(e)}",
            error=f"Error during dolt_commit: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltCheckout tool
@mcp.tool("DoltCheckout")
async def dolt_checkout(input):
    """Checkout a Dolt branch, making it active for the current session.

    Args:
        branch_name: Name of the branch to checkout.
        force: Whether to force checkout, discarding uncommitted changes.

    Returns:
        success: Whether the checkout operation succeeded
        message: Human-readable result message
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        parsed_input = DoltCheckoutInput(**input)
        result = dolt_checkout_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltCheckout MCP tool: {e}")
        return DoltCheckoutOutput(
            success=False,
            message=f"Checkout failed: {str(e)}",
            error=f"Error during dolt_checkout: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltAdd tool
@mcp.tool("DoltAdd")
async def dolt_add(input):
    """Stage working changes in Dolt for the current session.

    Args:
        tables: Optional list of specific tables to add. If not provided, all changes will be staged.

    Returns:
        success: Whether the add operation succeeded
        message: Human-readable result message
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        parsed_input = DoltAddInput(**input)
        result = dolt_add_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltAdd MCP tool: {e}")
        return DoltAddOutput(
            success=False,
            message=f"Add failed: {str(e)}",
            error=f"Error during dolt_add: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltReset tool
@mcp.tool("DoltReset")
async def dolt_reset(input):
    """Reset working changes in Dolt for the current session.

    Args:
        tables: Optional list of specific tables to reset. If not provided, all working changes will be discarded.
        hard: Whether to perform a hard reset, discarding all changes (default: True)

    Returns:
        success: Whether the reset operation succeeded
        message: Human-readable result message
        tables_reset: List of tables that were reset (if specific tables were targeted)
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        parsed_input = DoltResetInput(**input)
        result = dolt_reset_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltReset MCP tool: {e}")
        return DoltResetOutput(
            success=False,
            message=f"Reset failed: {str(e)}",
            error=f"Error during dolt_reset: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltPush tool
@mcp.tool("DoltPush")
async def dolt_push(input):
    """Push changes to a remote repository using Dolt.

    Args:
        remote_name: Name of the remote to push to (default: 'origin')
        branch: Branch to push (default: 'main')
        force: Whether to force push, overriding safety checks

    Returns:
        JSON string with push results including success status and message
    """
    try:
        # Create input object
        input_data = DoltPushInput(**input)

        # Execute the push operation
        result = dolt_push_tool(input_data, get_memory_bank())

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
        result = dolt_status_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in DoltStatus MCP tool: {e}")
        return DoltStatusOutput(
            success=False,
            active_branch="unknown",
            is_clean=False,
            total_changes=0,
            message=f"Status check failed: {str(e)}",
            error=str(e),
        ).model_dump(mode="json")


# Register the DoltPull tool
@mcp.tool("DoltPull")
async def dolt_pull(input):
    """Pull changes from a remote repository using Dolt.

    Args:
        remote_name: Name of the remote to pull from (default: 'origin')
        branch: Specific branch to pull (default: 'main')
        force: Whether to force pull, ignoring conflicts
        no_ff: Create a merge commit even for fast-forward merges
        squash: Merge changes to working set without updating commit history

    Returns:
        JSON string with pull results including success status and message
    """
    try:
        # Create input object
        input_data = DoltPullInput(**input)

        # Execute the pull operation
        result = dolt_pull_tool(input_data, get_memory_bank())

        # Return JSON representation
        return result.model_dump_json(indent=2)

    except Exception as e:
        logger.error(f"Error in DoltPull tool: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


@mcp.tool("DoltBranch")
async def dolt_branch(input):
    """Create a new branch using Dolt.

    Args:
        branch_name: Name of the new branch to create
        start_point: Commit, branch, or tag to start the branch from (optional)
        force: Whether to force creation, overriding safety checks

    Returns:
        JSON string with branch creation results including success status and message
    """
    try:
        # Create input object
        input_data = DoltBranchInput(**input)

        # Execute the branch creation operation
        result = dolt_branch_tool(input_data, get_memory_bank())

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
        # Parse dict input into Pydantic model
        parsed_input = DoltListBranchesInput(**input)
        result = dolt_list_branches_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in DoltListBranches MCP tool: {e}")
        # Import locally for error handling too
        from infra_core.memory_system.tools.agent_facing.dolt_repo_tool import (
            DoltListBranchesOutput,
        )

        return DoltListBranchesOutput(
            success=False,
            active_branch="unknown",
            message=f"Branch listing failed: {str(e)}",
            error=f"Error during dolt_list_branches: {str(e)}",
        ).model_dump(mode="json")


@mcp.tool("ListNamespaces")
async def list_namespaces(input):
    """List all available namespaces with their metadata

    Returns:
        success: Whether the operation succeeded
        namespaces: List of namespace information objects
        total_count: Total number of namespaces
        message: Human-readable result message
        active_branch: Current active branch
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = ListNamespacesInput(**input)
        result = list_namespaces_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in ListNamespaces MCP tool: {e}")
        return ListNamespacesOutput(
            success=False,
            namespaces=[],
            total_count=0,
            active_branch="unknown",
            message=f"Namespace listing failed: {str(e)}",
            error=f"Error during list_namespaces: {str(e)}",
        ).model_dump(mode="json")


# Register the CreateNamespace tool
@mcp.tool("CreateNamespace")
async def create_namespace(input):
    """Create a new namespace in the database

    Args:
        id: Unique namespace identifier (e.g., 'cogni-project-management')
        name: Human-readable namespace name (e.g., 'Cogni Project Management')
        slug: URL-safe namespace identifier (defaults to id if not provided)
        owner_id: ID of the namespace owner (defaults to 'system')
        description: Optional description of the namespace
        is_active: Whether the namespace is active (defaults to True)

    Note: This creates a new namespace but does not change the current namespace context.
    Use DOLT_NAMESPACE environment variable to set the active namespace for all operations.

    Returns:
        success: Whether the operation succeeded
        namespace_id: ID of the created namespace
        message: Human-readable result message
        active_branch: Current active branch
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = CreateNamespaceInput(**input)
        result = create_namespace_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in CreateNamespace MCP tool: {e}")
        return CreateNamespaceOutput(
            success=False,
            namespace_id=None,
            message=f"Namespace creation failed: {str(e)}",
            active_branch="unknown",
            error=f"Error during create_namespace: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltDiff tool
@mcp.tool("DoltDiff")
async def dolt_diff(input):
    """Get a summary of differences between two revisions in Dolt.

    Args:
        mode: Diff mode. 'working' for unstaged changes, 'staged' for staged changes.
        from_revision: The starting revision (e.g., 'HEAD', 'main').
        to_revision: The ending revision (e.g., 'WORKING', 'STAGED').
    """
    try:
        input_data = DoltDiffInput(**input)
        result = dolt_diff_tool(input_data, get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error getting Dolt diff: {e}", exc_info=True)
        return DoltDiffOutput(
            success=False,
            diff_summary=[],
            message=f"An unexpected error occurred: {e}",
            active_branch="unknown",
            error=str(e),
        ).model_dump(mode="json")


# Register the DoltAutoCommitAndPush tool
@mcp.tool("DoltAutoCommitAndPush")
async def dolt_auto_commit_and_push(input):
    """Automatically handle the complete Dolt workflow: Status -> Add -> Commit -> Push

    This is a composite tool that performs the entire sequence atomically,
    perfect for automated flows where you want to persist all changes.

    Args:
        commit_message: Commit message for the Dolt changes (required)
        author: Optional author attribution for the commit
        tables: Optional list of specific tables to add/commit (default: all standard tables)
        remote_name: Name of the remote to push to (default: 'origin')
        branch: Branch to push (default: current branch from status)
        skip_if_clean: Skip commit/push if repository is clean (default: True)

    Returns:
        JSON with comprehensive results of all operations including success status,
        operations performed, commit hash, and push details
    """
    try:
        # Parse input
        input_data = DoltAutoCommitInput(**input)

        # Execute the composite operation
        result = dolt_auto_commit_and_push_tool(input_data, get_memory_bank())

        # Return JSON representation
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in DoltAutoCommitAndPush tool: {e}", exc_info=True)
        return DoltAutoCommitOutput(
            success=False,
            message=f"Auto commit and push failed: {str(e)}",
            operations_performed=["failed"],
            was_clean=False,
            active_branch="unknown",
            error=str(e),
        ).model_dump(mode="json")


# Register the DoltCreatePullRequest tool
@mcp.tool("DoltCreatePullRequest")
async def dolt_create_pull_request(input):
    """Create a pull request for merging branches in Dolt

    Args:
        source_branch: Source branch to merge from
        target_branch: Target branch to merge into (default: 'main')
        title: Title of the pull request
        description: Optional description of the pull request
        reviewers: Optional list of reviewers for the pull request
        auto_merge: Whether to automatically merge if all checks pass (default: False)

    Returns:
        success: Whether the pull request was created successfully
        pr_id: Unique identifier for the pull request
        pr_url: URL to view the pull request (if applicable)
        message: Human-readable result message
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = DoltCreatePullRequestInput(**input)
        result = dolt_create_pull_request_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltCreatePullRequest MCP tool: {e}")
        return DoltCreatePullRequestOutput(
            success=False,
            message=f"Pull request creation failed: {str(e)}",
            error=f"Error during dolt_create_pull_request: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltMerge tool
@mcp.tool("DoltMerge")
async def dolt_merge(input):
    """Merge one branch into another using Dolt's DOLT_MERGE procedure

    Args:
        source_branch: Source branch to merge from
        target_branch: Target branch to merge into (default: current branch)
        commit_message: Custom commit message for the merge
        no_ff: Create a merge commit even for fast-forward merges (default: False)
        squash: Squash commits from source branch (default: False)
        author: Author attribution for the merge commit

    Returns:
        success: Whether the merge operation succeeded
        merge_hash: Hash of the merge commit
        message: Human-readable result message
        source_branch: Source branch that was merged
        target_branch: Target branch that received the merge
        fast_forward: Whether the merge was a fast-forward
        conflicts: Number of conflicts that need resolution
        active_branch: Current active branch
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = DoltMergeInput(**input)
        result = dolt_merge_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltMerge MCP tool: {e}")
        return DoltMergeOutput(
            success=False,
            message=f"Merge failed: {str(e)}",
            source_branch=input.get("source_branch", "unknown"),
            target_branch=input.get("target_branch", "unknown"),
            fast_forward=False,
            active_branch="unknown",
            error=f"Error during dolt_merge: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltCompareBranches tool
@mcp.tool("DoltCompareBranches")
async def dolt_compare_branches(input):
    """Compare two branches to show differences and check merge compatibility

    Args:
        source_branch: Source branch to compare from
        target_branch: Target branch to compare to
        include_data: Whether to include data differences (default: True)
        include_schema: Whether to include schema differences (default: True)
        table_filter: Optional table name to filter comparison

    Returns:
        success: Whether the comparison succeeded
        message: Human-readable result message
        source_branch: Source branch
        target_branch: Target branch
        has_differences: Whether there are any differences
        can_merge: Whether branches can be merged without conflicts
        diff_summary: Summary of differences
        active_branch: Current active branch
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = DoltCompareBranchesInput(**input)
        result = dolt_compare_branches_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltCompareBranches MCP tool: {e}")
        return DoltCompareBranchesOutput(
            success=False,
            message=f"Branch comparison failed: {str(e)}",
            source_branch=input.get("source_branch", "unknown"),
            target_branch=input.get("target_branch", "unknown"),
            has_differences=False,
            can_merge=False,
            active_branch="unknown",
            error=f"Error during dolt_compare_branches: {str(e)}",
        ).model_dump(mode="json")


# Register the DoltApprovePullRequest tool
@mcp.tool("DoltApprovePullRequest")
async def dolt_approve_pull_request(input):
    """Approve and merge a pull request using the DoltHub API

    Args:
        pr_id: Pull request ID to approve and merge
        approve_message: Optional message for the approval

    Returns:
        success: Whether the pull request approval succeeded
        pr_id: Pull request ID that was approved
        merge_hash: Hash of the merge commit
        operation_name: DoltHub operation name for polling
        message: Human-readable result message
        active_branch: Current active branch
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        # Parse dict input into Pydantic model
        parsed_input = DoltApprovePullRequestInput(**input)
        result = dolt_approve_pull_request_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltApprovePullRequest MCP tool: {e}")
        return DoltApprovePullRequestOutput(
            success=False,
            message=f"Pull request approval failed: {str(e)}",
            pr_id=input.get("pr_id", "unknown"),
            active_branch="unknown",
            error=f"Error during dolt_approve_pull_request: {str(e)}",
        ).model_dump(mode="json")


# Register a health check tool
@mcp.tool("HealthCheck")
async def health_check():
    """Check if the memory bank is initialized"""
    memory_bank_ok = get_memory_bank() is not None
    link_manager_ok = get_link_manager() is not None and get_pm_links() is not None

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
    import os

    # Allow transport to be controlled via environment variable
    # Default to stdio for Cursor, use MCP_TRANSPORT=sse for ToolHive
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    # For SSE/HTTP transports, simply pass the environment variables and let FastMCP handle them
    # According to FastMCP docs, it reads from environment variables automatically
    mcp.run(transport=transport)
