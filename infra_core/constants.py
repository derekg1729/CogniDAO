import os
from pathlib import Path

# --- Core Paths ---

# Calculate the absolute path of the project root directory (one level above infra_core)
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Define the root directory for memory banks (outside infra_core)
MEMORY_BANKS_ROOT = BASE_DIR / "data" / "memory_banks"

# Define the directory for agent-specific files like thoughts
# (Even if not writing directly, agents might use this for their root)
AGENTS_DATA_ROOT = BASE_DIR / "data" / "agents"

# Example: Specific agent data directory (can be constructed dynamically or defined here)
THOUGHTS_DIR = AGENTS_DATA_ROOT / "presence" / "thoughts"

# Ensure base data directories exist (optional, can be done on demand)
# MEMORY_BANKS_ROOT.mkdir(parents=True, exist_ok=True)
# AGENTS_DATA_ROOT.mkdir(parents=True, exist_ok=True)
# THOUGHTS_DIR.mkdir(parents=True, exist_ok=True) # Example if needed


# --- Other Constants (Example) ---
DEFAULT_PROJECT_NAME = "cogni-default" 