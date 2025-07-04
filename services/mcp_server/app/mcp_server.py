import os
import sys
import logging
import importlib.util
from pathlib import Path
from datetime import datetime
import json
from functools import wraps

from mcp.server.fastmcp import FastMCP
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.dolt_mysql_base import DoltConnectionConfig
from infra_core.memory_system.sql_link_manager import SQLLinkManager
# get_active_work_items_tool now auto-generated
from infra_core.memory_system.pm_executable_links import ExecutableLinkManager
from infra_core.memory_system.tools.agent_facing.get_linked_blocks_tool import (
    get_linked_blocks_tool,
    GetLinkedBlocksInput,
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
    dolt_reset_tool,
    DoltResetInput,
    DoltResetOutput,
    dolt_merge_tool,
    DoltMergeInput,
    DoltMergeOutput,
)
from infra_core.memory_system.tools.agent_facing.bulk_update_namespace_tool import (
    bulk_update_namespace,
    BulkUpdateNamespaceInput,
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

# Import auto-generation system for Phase 2 architecture
try:
    # Try relative import first (when run as module)
    from .mcp_auto_generator import auto_register_cogni_tools_to_mcp, get_auto_generation_stats
except ImportError:
    # Fall back to direct import (when run as script)
    import sys
    from pathlib import Path

    # Add the app directory to Python path for direct script execution
    app_dir = Path(__file__).parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    from mcp_auto_generator import auto_register_cogni_tools_to_mcp, get_auto_generation_stats

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

    # STUBBED: Always return "feat/prompt-templates" for current development work
    logger.info("STUBBED: Fallback to main branch")
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


def inject_current_namespace(input_data):
    """
    Inject current namespace into input if not specified.

    FIX: Operates on a copy to prevent mutation side effects (addresses P1 issue)
    """
    try:
        # CRITICAL: Normalize FIRST before any key access
        normalized_input = _normalize_mcp_input(input_data)

        # FIX: Work on a copy to prevent mutation side effects
        if isinstance(normalized_input, dict):
            result = dict(normalized_input)  # Shallow copy

            if "namespace_id" not in result or result["namespace_id"] is None:
                current_ns = get_current_namespace_context()
                if current_ns:
                    result["namespace_id"] = current_ns

            return result
        else:
            # For list inputs, return as-is (bulk operations)
            return normalized_input

    except Exception as e:
        logger.warning(f"Failed to inject namespace: {str(e)}")
        return input_data  # Fallback to original


def standardize_mcp_response(response_data):
    """
    DRY helper to standardize MCP tool output responses with consistent namespace context.

    This ensures all MCP tools return responses with namespace_id for consistency,
    enabling clients to understand which namespace context was used for the operation.

    Args:
        response_data: The tool response (dict, Pydantic model, or other)
        include_namespace: Whether to include namespace_id in the response (default: True)

    Returns:
        Standardized response (currently passes through unchanged, but kept for future use)
    """
    # Currently just pass through - namespace injection removed to fix override issues
    # This wrapper is kept for future standardization needs
    return response_data


def mcp_autofix(func):
    """
    Decorator that automatically handles input normalization for MCP tools.

    This fixes the double-serialization issue where autogen agents send:
    dict -> JSON string -> escaped JSON string

    Must be applied to ALL MCP tool wrappers to prevent regression.
    """

    @wraps(func)
    async def wrapper(input):
        try:
            # CRITICAL: Normalize input FIRST, before any key access
            normalized_input = _normalize_mcp_input(input)

            # Call the original function with normalized input
            return await func(normalized_input)
        except Exception as e:
            logger.error(f"Error in {func.__name__} with autofix: {str(e)}")
            # Return a generic error response that matches expected output structure
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}",
                "timestamp": datetime.now(),
            }

    # Mark the wrapper as having autofix applied for CI validation
    wrapper._has_mcp_autofix = True
    return wrapper


def _normalize_mcp_input(input_data, max_depth=3):
    """
    Normalize MCP input to handle double/triple serialization from autogen agents.

    EMERGENCY FIX for the pattern: dict -> JSON string -> escaped JSON string
    that causes **input unpacking to fail in Pydantic models.

    Args:
        input_data: Raw input that could be dict, JSON string, or double-serialized JSON
        max_depth: Maximum recursion depth to prevent infinite loops (addresses P2 issue)

    Returns:
        dict: Normalized input ready for Pydantic validation

    Raises:
        ValueError: If input cannot be normalized or max_depth exceeded
    """
    if isinstance(input_data, dict):
        return input_data

    if not isinstance(input_data, str):
        # FIX: Allow lists for bulk operations (addresses P1 issue)
        if isinstance(input_data, list):
            return input_data
        raise ValueError(f"Input must be dict, list, or string, got {type(input_data)}")

    depth = 0
    current = input_data

    while isinstance(current, str) and depth < max_depth:
        try:
            parsed = json.loads(current)
            # FIX: Prevent infinite loops (addresses P2 issue)
            if parsed == current:
                break
            current = parsed
            depth += 1
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON at depth {depth}: {str(e)}")

    if depth >= max_depth:
        raise ValueError(f"Max recursion depth ({max_depth}) exceeded during normalization")

    # FIX: Allow lists at top level (addresses P1 issue)
    if not isinstance(current, (dict, list)):
        raise ValueError(f"Final parsed result must be dict or list, got {type(current)}")

    return current


# Create a FastMCP server instance with a specific name
mcp = FastMCP("cogni-memory")

# Phase 2: Auto-register all CogniTools as MCP tools
logger.info("🤖 [PHASE 2] Starting auto-registration of CogniTools...")
try:
    registration_results = auto_register_cogni_tools_to_mcp(mcp, get_memory_bank)

    # Log registration results
    success_count = sum(1 for status in registration_results.values() if status == "SUCCESS")
    total_count = len(registration_results)

    logger.info(
        f"🤖 [PHASE 2] Auto-registration complete: {success_count}/{total_count} tools registered"
    )

    # Log any failures
    failures = {
        name: status for name, status in registration_results.items() if status != "SUCCESS"
    }
    if failures:
        logger.warning(f"🤖 [PHASE 2] Registration failures: {failures}")

    # Log statistics
    stats = get_auto_generation_stats()
    logger.info(
        f"🤖 [PHASE 2] Maintenance reduction: {stats['maintenance_reduction_percent']}% ({stats['lines_saved']} lines saved)"
    )

except Exception as e:
    logger.error(f"🤖 [PHASE 2] Auto-registration failed: {e}")
    # Continue with manual tools as fallback
    logger.info("🤖 [PHASE 2] Continuing with manual tool registrations as fallback")


## TODO: manual tool registration required for these. CogniTools do not exist yet


# GetActiveWorkItems tool now auto-generated from CogniTool instance


# Register the GetLinkedBlocks tool
@mcp.tool("GetLinkedBlocks")
@mcp_autofix
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
        # Inject namespace if not provided (input already normalized by decorator)
        input_with_namespace = inject_current_namespace(input)

        parsed_input = GetLinkedBlocksInput(**input_with_namespace)
        result = get_linked_blocks_tool(
            source_block_id=parsed_input.source_block_id,
            relation_filter=parsed_input.relation_filter,
            direction_filter=parsed_input.direction_filter,
            limit=parsed_input.limit,
            memory_bank=get_memory_bank(),
        )
        return result.model_dump()

    except Exception as e:
        logger.error(f"Error getting linked blocks: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to get linked blocks: {str(e)}",
            "linked_blocks": [],
            "timestamp": datetime.now(),
        }


# NOTE: CreateBlockLink now has CogniTool instance - using auto-generated version


# Register the BulkUpdateNamespace tool
@mcp.tool("BulkUpdateNamespace")
@mcp_autofix
async def bulk_update_namespace_mcp(input):
    """Update namespace of multiple memory blocks in a single operation with independent success tracking

    Args:
        blocks: List of block specifications to update (1-500 blocks)
        target_namespace_id: Target namespace ID to move all blocks to
        stop_on_first_error: If True, stop processing on first error. If False, continue and report all results.
        author: Author of the namespace updates
        agent_id: Agent identifier for tracking
        session_id: Session ID for grouping updates

    Returns:
        success: Whether ALL blocks were updated successfully (failed_count == 0)
        partial_success: Whether at least one block was updated successfully
        total_blocks: Total number of blocks attempted
        successful_blocks: Number of blocks updated successfully
        failed_blocks: Number of blocks that failed to update
        results: Individual results for each block
        target_namespace_id: Target namespace that was attempted
        namespace_validated: Whether the target namespace was validated to exist
        active_branch: Current active branch
        timestamp: When the bulk operation completed
    """
    try:
        # Input already normalized by decorator
        parsed_input = BulkUpdateNamespaceInput(**input)
        result = bulk_update_namespace(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump()

    except Exception as e:
        logger.error(f"Error in bulk update namespace: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to bulk update namespace: {str(e)}",
            "timestamp": datetime.now(),
        }


# Register the DoltCommit tool
@mcp.tool("DoltCommit")
@mcp_autofix
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
        # EMERGENCY FIX: Normalize input to handle double-serialization
        normalized_input = _normalize_mcp_input(input)

        # Parse dict input into Pydantic model
        parsed_input = DoltCommitInput(**normalized_input)
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
@mcp_autofix
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
        # EMERGENCY FIX: Normalize input to handle double-serialization
        normalized_input = _normalize_mcp_input(input)

        parsed_input = DoltCheckoutInput(**normalized_input)
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
@mcp_autofix
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
        # EMERGENCY FIX: Normalize input to handle double-serialization
        normalized_input = _normalize_mcp_input(input)

        parsed_input = DoltAddInput(**normalized_input)
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
@mcp_autofix
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
@mcp_autofix
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
        # EMERGENCY FIX: Normalize input to handle double-serialization
        normalized_input = _normalize_mcp_input(input)

        # Create input object
        input_data = DoltPushInput(**normalized_input)

        # Execute the push operation
        result = dolt_push_tool(input_data, get_memory_bank())

        # Return JSON representation
        return result.model_dump_json(indent=2)

    except Exception as e:
        logger.error(f"Error in DoltPush tool: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# Register the DoltStatus tool
@mcp.tool("DoltStatus")
@mcp_autofix
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
        # EMERGENCY FIX: Normalize input to handle double-serialization
        normalized_input = _normalize_mcp_input(input)

        # Parse dict input into Pydantic model
        parsed_input = DoltStatusInput(**normalized_input)

        # Execute the status operation
        result = dolt_status_tool(parsed_input, memory_bank=get_memory_bank())

        logger.info(f"DoltStatus result: {result}")

        # Return JSON representation
        return result.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Error in DoltStatus tool: {e}", exc_info=True)

        # Try to get current branch even in error case (like dolt_list_branches does)
        try:
            current_branch = get_memory_bank().branch
        except Exception:
            current_branch = "unknown"

        # Return structured error using the output model
        error_output = DoltStatusOutput(
            success=False,
            current_branch=current_branch,
            is_clean=True,
            staged_tables=[],
            unstaged_tables=[],
            untracked_tables=[],
            total_changes=0,
            ahead=0,
            behind=0,
            conflicts=[],
            message="Status check failed",
            active_branch=current_branch,
            error=f"Error during dolt_status: {str(e)}",
            timestamp=datetime.now(),
        )

        return error_output.model_dump(mode="json")


# Register the DoltPull tool
@mcp.tool("DoltPull")
@mcp_autofix
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
@mcp_autofix
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
@mcp_autofix
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
            active_branch=get_memory_bank().branch,
            message=f"Branch listing failed: {str(e)}",
            error=f"Error during dolt_list_branches: {str(e)}",
        ).model_dump(mode="json")


@mcp.tool("ListNamespaces")
@mcp_autofix
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
        return standardize_mcp_response(result.model_dump(mode="json"))

    except Exception as e:
        logger.error(f"Error in ListNamespaces MCP tool: {e}")
        error_response = ListNamespacesOutput(
            success=False,
            namespaces=[],
            total_count=0,
            active_branch=get_memory_bank().branch,
            message=f"Namespace listing failed: {str(e)}",
            error=f"Error during list_namespaces: {str(e)}",
        ).model_dump(mode="json")
        return standardize_mcp_response(error_response)


# Register the CreateNamespace tool
@mcp.tool("CreateNamespace")
@mcp_autofix
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
        return standardize_mcp_response(result.model_dump(mode="json"))

    except Exception as e:
        logger.error(f"Error in CreateNamespace MCP tool: {e}")
        error_response = CreateNamespaceOutput(
            success=False,
            namespace_id=None,
            message=f"Namespace creation failed: {str(e)}",
            active_branch=get_memory_bank().branch,
            error=f"Error during create_namespace: {str(e)}",
        ).model_dump(mode="json")
        return standardize_mcp_response(error_response)


# Register the DoltDiff tool
@mcp.tool("DoltDiff")
@mcp_autofix
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
            active_branch=get_memory_bank().branch,
            error=str(e),
        ).model_dump(mode="json")


# Register the DoltAutoCommitAndPush tool
@mcp.tool("DoltAutoCommitAndPush")
@mcp_autofix
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
            active_branch=get_memory_bank().branch,
            error=str(e),
        ).model_dump(mode="json")


# Register a health check tool
# @mcp.tool("HealthCheck")    # AUTO-GENERATED (commented out)
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


# Register the DoltMerge tool
@mcp.tool("DoltMerge")
@mcp_autofix
async def dolt_merge(input):
    """Merge a branch into the current branch using Dolt.

    Args:
        source_branch: Name of the branch to merge into the current branch
        squash: Whether to squash all commits from source branch into single commit (default: False)
        no_ff: Create a merge commit even for fast-forward merges (default: False)
        commit_message: Custom commit message for the merge (optional)

    Returns:
        success: Whether the merge operation succeeded
        source_branch: Name of the branch that was merged
        target_branch: Name of the branch that was merged into
        squash: Whether squash merge was used
        no_ff: Whether no-fast-forward was used
        fast_forward: Whether the merge was a fast-forward
        conflicts: Number of conflicts encountered
        merge_hash: Hash of the merge commit if successful
        message: Human-readable result message
        error: Error message if operation failed
        timestamp: Timestamp of operation
    """
    try:
        parsed_input = DoltMergeInput(**input)
        result = dolt_merge_tool(parsed_input, memory_bank=get_memory_bank())
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error in DoltMerge MCP tool: {e}")
        return DoltMergeOutput(
            success=False,
            message=f"Merge failed: {str(e)}",
            source_branch=input.get("source_branch", "unknown"),
            target_branch=get_memory_bank().branch,
            squash=input.get("squash", False),
            no_ff=input.get("no_ff", False),
            fast_forward=False,
            conflicts=0,
            merge_hash=None,
            commit_message=input.get("commit_message"),
            active_branch=get_memory_bank().branch,
            error=f"Error during dolt_merge: {str(e)}",
        ).model_dump(mode="json")


# When this file is executed directly, use the MCP CLI
if __name__ == "__main__":
    import os

    # Allow transport to be controlled via environment variable
    # Default to stdio for Cursor, use MCP_TRANSPORT=sse for ToolHive
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    # 🔍 ENHANCED STARTUP LOGGING for debugging deployment issues
    print("🚀 [MCP STARTUP] Cogni MCP Server starting...")
    print(f"🔧 [MCP STARTUP] Transport: {transport}")
    print("🔧 [MCP STARTUP] Environment Variables:")

    # Log key environment variables
    key_env_vars = [
        "MCP_TRANSPORT",
        "MCP_HOST",
        "MCP_PORT",
        "DOLT_HOST",
        "DOLT_PORT",
        "DOLT_DATABASE",
        "DOLT_BRANCH",
        "DOLT_NAMESPACE",
    ]

    for var in key_env_vars:
        value = os.getenv(var, "(not set)")
        print(f"    {var} = '{value}'")

    try:
        print(f"🎯 [MCP STARTUP] Calling mcp.run(transport='{transport}')...")

        # For SSE/HTTP transports, simply pass the environment variables and let FastMCP handle them
        # According to FastMCP docs, it reads from environment variables automatically
        mcp.run(transport=transport)

        print("✅ [MCP STARTUP] Server started successfully!")

    except Exception as e:
        print(f"❌ [MCP STARTUP] Server startup failed: {e}")
        print(f"📊 [MCP STARTUP] Exception type: {type(e).__name__}")
        import traceback

        print("📊 [MCP STARTUP] Full traceback:")
        traceback.print_exc()
        raise
