import os
import sys
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.tools.agent_facing.get_memory_block_tool import (
    get_memory_block_tool,
)
from infra_core.memory_system.tools.agent_facing.create_work_item_tool import (
    create_work_item_tool,
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
        result = create_work_item_tool(input, memory_bank=memory_bank)
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
        result = get_memory_block_tool(input, memory_bank=memory_bank)
        return result
    except Exception as e:
        logger.error(f"Error getting memory block: {e}")
        return {"error": str(e)}


# Register a health check tool
@mcp.tool("HealthCheck")
async def health_check():
    """Check if the memory bank is initialized"""
    return {
        "status": "ok",
        "memory_bank_initialized": memory_bank is not None,
        "dolt_path": COGNI_DOLT_DIR,
        "chroma_path": CHROMA_PATH,
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
