#!/bin/bash
# Pre-commit hook script to register schemas and check for unstaged Dolt changes.

# --- Determine Dolt Path --- #
# Use python to get the configured path (respects CLI -> Env Var -> Default from constants.py)
# Note: This runs the get_dolt_db_path logic, but we only care about the path result.
# If CLI/ENV are set for the user, this hook will respect them.

PYTHON_GET_PATH_CMD='from infra_core.constants import MEMORY_DOLT_ROOT; import os; print(os.getenv("DOLT_DB_PATH", MEMORY_DOLT_ROOT))'
DOLT_DB_PATH=$(python -c "$PYTHON_GET_PATH_CMD")

if [ -z "$DOLT_DB_PATH" ]; then
    echo "Error: Could not determine Dolt DB path." 
    exit 1
fi
echo "Using Dolt DB Path: $DOLT_DB_PATH"

# --- Check Dolt Workspace Cleanliness --- #
# Check if Dolt CLI is available
if ! command -v dolt &> /dev/null
then
    echo "Error: dolt command not found. Please install dolt."
    exit 1
fi

# Go into the Dolt directory to run dolt status
if [ -d "$DOLT_DB_PATH" ]; then
    echo "Checking Dolt status in $DOLT_DB_PATH..."
    DOLT_STATUS_OUTPUT=$(cd "$DOLT_DB_PATH" && dolt status)
    DOLT_STATUS_EXIT_CODE=$?
    
    if [ $DOLT_STATUS_EXIT_CODE -ne 0 ]; then
        echo "Error running 'dolt status' in $DOLT_DB_PATH. Cannot verify cleanliness."
        exit $DOLT_STATUS_EXIT_CODE
    fi

    # Check if status output indicates a clean working set
    # Adjust this check based on the exact output of `dolt status` for a clean repo
    if [[ "$DOLT_STATUS_OUTPUT" != *"nothing to commit, working tree clean"* ]]; then
        echo "Error: Dolt working directory ($DOLT_DB_PATH) is not clean."
        echo "Please commit or stash Dolt changes before registering schemas."
        echo "------ Dolt Status ------"
        echo "$DOLT_STATUS_OUTPUT"
        echo "-------------------------"
        exit 1
    else
        echo "Dolt working directory is clean."
    fi
else
    echo "Warning: Dolt directory $DOLT_DB_PATH not found. Skipping cleanliness check."
    # If the directory doesn't exist, register_schemas.py might create it,
    # which is fine, but the git status check later will catch the unstaged creation.
fi

# --- Run Schema Registration --- #
# Run the script, explicitly passing the determined path for clarity 
# (though the script would determine the same path internally)
echo "Running schema registration script..."
python infra_core/memory_system/scripts/register_schemas.py --db-path "$DOLT_DB_PATH"

REGISTRATION_EXIT_CODE=$?
if [ $REGISTRATION_EXIT_CODE -ne 0 ]; then
    echo "Schema registration script (register_schemas.py) failed. Commit aborted."
    exit $REGISTRATION_EXIT_CODE
fi

# --- Check for Unstaged Git Changes in Dolt Path --- #
# Use the determined path
if [ ! -d "$DOLT_DB_PATH" ]; then
    # This case should ideally not happen if registration succeeded and path was valid,
    # but check defensively.
    echo "Error: Dolt database directory $DOLT_DB_PATH not found after successful registration attempt?" 
    exit 1
fi

GIT_STATUS_OUTPUT=$(git status --porcelain "$DOLT_DB_PATH")

if [ -n "$GIT_STATUS_OUTPUT" ]; then
    echo "Uncommitted git changes found in $DOLT_DB_PATH after schema registration:"
    echo "$GIT_STATUS_OUTPUT"
    echo "Please stage these changes (e.g., git add $DOLT_DB_PATH) and commit again."
    exit 1
else
    echo "Schema registration successful and no uncommitted Dolt git changes found."
    exit 0
fi 