import os
from pathlib import Path

# --- Core Paths ---

# Calculate the absolute path of the project root directory (one level above legacy_logseq)
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define the root directory for memory banks (outside legacy_logseq)
MEMORY_BANKS_ROOT = BASE_DIR / "data" / "memory_banks"

# Define memory system data paths
MEMORY_DOLT_ROOT = BASE_DIR / "data" / "memory_dolt"

# Property-Schema Split Database (new implementation with block_properties table)
# Can be overridden with COGNI_PROPERTY_SCHEMA_DB_PATH environment variable for rollback safety
_DEFAULT_PROPERTY_SCHEMA_DOLT_PATH = BASE_DIR / "data" / "blocks" / "memory_dolt"
PROPERTY_SCHEMA_DOLT_ROOT = Path(
    os.getenv("COGNI_PROPERTY_SCHEMA_DB_PATH", str(_DEFAULT_PROPERTY_SCHEMA_DOLT_PATH))
)

MEMORY_CHROMA_ROOT = BASE_DIR / "data" / "memory_chroma"

# Define the directory for agent-specific files like thoughts
# (Even if not writing directly, agents might use this for their root)
AGENTS_DATA_ROOT = BASE_DIR / "data" / "agents"

# Example: Specific agent data directory (can be constructed dynamically or defined here)
THOUGHTS_DIR = AGENTS_DATA_ROOT / "presence" / "thoughts"

# Broadcast queue memory bank constants
BROADCAST_QUEUE_PROJECT = "broadcast_queue"
BROADCAST_QUEUE_SESSION = "main"
BROADCAST_QUEUE_ROOT = MEMORY_BANKS_ROOT / BROADCAST_QUEUE_PROJECT / BROADCAST_QUEUE_SESSION

# Test-specific constants
TEST_SESSION = "test_session"
BROADCAST_QUEUE_TEST_SESSION = TEST_SESSION
BROADCAST_QUEUE_TEST_ROOT = (
    MEMORY_BANKS_ROOT / BROADCAST_QUEUE_PROJECT / BROADCAST_QUEUE_TEST_SESSION
)

# Mock memory path for tests
TEST_MOCK_MEMORY_ROOT = Path.home() / "test" / "mock" / "memory"

# Ensure base data directories exist (optional, can be done on demand)
# MEMORY_BANKS_ROOT.mkdir(parents=True, exist_ok=True)
# AGENTS_DATA_ROOT.mkdir(parents=True, exist_ok=True)
# THOUGHTS_DIR.mkdir(parents=True, exist_ok=True) # Example if needed
# MEMORY_DOLT_ROOT.mkdir(parents=True, exist_ok=True)
# MEMORY_CHROMA_ROOT.mkdir(parents=True, exist_ok=True)


# --- Other Constants (Example) ---
DEFAULT_PROJECT_NAME = "cogni-default"
