import json
from pathlib import Path
from typing import Dict, Any, Optional
from typing_extensions import Annotated
from autogen_core.tools import FunctionTool

from infra_core.memory.memory_bank import CogniMemoryBank
from infra_core.constants import (
    MEMORY_BANKS_ROOT, 
    BROADCAST_QUEUE_PROJECT, 
    BROADCAST_QUEUE_SESSION,
    BROADCAST_QUEUE_ROOT
)

def fetch_from_broadcast_queue(
    status: Annotated[str, "Status to filter by ('approved', 'pending', 'needs_revision', 'posted')"],
    limit: Annotated[Optional[int], "Maximum number of items to return (0 for all)"] = 5,
    sort_by: Annotated[Optional[str], "Sort field ('priority', 'creation_time', 'scheduled_time')"] = "priority",
    sort_order: Annotated[Optional[str], "Sort direction ('asc' or 'desc')"] = "asc"
) -> str:
    """
    Fetches items from the broadcast queue with the specified status.
    
    This tool:
    1. Reads state JSON files from the state/ directory
    2. Filters items based on the requested status
    3. Sorts and limits results as specified
    4. Returns items with their complete metadata
    """
    try:
        # Set up memory bank access
        
        # Get path to state directory
        state_dir = BROADCAST_QUEUE_ROOT / "state"
        
        # Ensure directories exist
        if not state_dir.exists():
            return json.dumps({
                "status": "error",
                "message": f"State directory not found: {state_dir}"
            }, indent=2)
        
        # Find all JSON files in state directory
        json_files = list(state_dir.glob('*.json'))
        
        # Process each state file
        items = []
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    state_data = json.load(f)
                
                # Check if item matches requested status
                if state_data.get('status') == status:
                    # Add queue_id to the item if not already present
                    if 'queue_id' not in state_data:
                        state_data['queue_id'] = json_file.stem
                        
                    items.append(state_data)
            except json.JSONDecodeError:
                # Skip invalid JSON files
                continue
                
        # Sort items by the specified field
        if sort_by and sort_by in ["priority", "creation_time", "scheduled_time"]:
            reverse = sort_order.lower() == "desc"
            items.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)
            
        # Limit results if specified
        if limit > 0:
            items = items[:limit]
            
        # Return results
        result = {
            "status": "success",
            "total_items": len(items),
            "items": items,
            "message": f"Found {len(items)} items with status '{status}'"
        }
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"Failed to fetch broadcast queue items: {str(e)}"
        }
        return json.dumps(error_result, indent=2)

def update_broadcast_queue_item(
    queue_id: Annotated[str, "ID of the queue item to update"],
    new_status: Annotated[str, "New status for the item ('approved', 'pending', 'needs_revision', 'posted')"],
    post_info: Annotated[Optional[Dict[str, Any]], "Information about the post to store (for 'posted' status)"] = None
) -> str:
    """
    Updates the status of an item in the broadcast queue.
    
    This tool:
    1. Reads the state file for the specified queue item
    2. Updates the status and adds post info if provided
    3. Writes the updated state back to the file
    4. Logs the update to the queue log
    """
    try:
        # Set up memory bank access
        queue_bank = CogniMemoryBank(
            memory_bank_root=Path(MEMORY_BANKS_ROOT),
            project_name=BROADCAST_QUEUE_PROJECT,
            session_id=BROADCAST_QUEUE_SESSION
        )
        
        # Get paths to directories
        state_dir = BROADCAST_QUEUE_ROOT / "state"
        log_dir = BROADCAST_QUEUE_ROOT / "log"
        
        # Ensure directories exist
        state_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Get path to state file
        state_file = state_dir / f"{queue_id}.json"
        
        # Check if state file exists
        if not state_file.exists():
            return json.dumps({
                "status": "error",
                "message": f"State file not found for queue ID: {queue_id}"
            }, indent=2)
            
        # Read current state
        with open(state_file, 'r') as f:
            state_data = json.load(f)
            
        # Record previous status
        previous_status = state_data.get('status', 'unknown')
        
        # Update status
        state_data['status'] = new_status
        
        # Add post info if provided and status is 'posted'
        if new_status == 'posted' and post_info:
            state_data['post_info'] = post_info
            
        # Write updated state back to file
        with open(state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
            
        # Log the update
        from datetime import datetime
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action_type": "status_update",
            "queue_id": queue_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "has_post_info": bool(post_info)
        }
        
        # Add to decisions.jsonl via memory bank
        queue_bank.log_decision(log_entry)
        
        # Also append to broadcast_queue.jsonl
        log_file_path = log_dir / "broadcast_queue.jsonl"
        with open(log_file_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        # Return success
        result = {
            "status": "success",
            "queue_id": queue_id,
            "previous_status": previous_status,
            "new_status": new_status,
            "message": f"Updated queue item {queue_id} status from '{previous_status}' to '{new_status}'"
        }
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"Failed to update broadcast queue item: {str(e)}"
        }
        return json.dumps(error_result, indent=2)

# Create tools
fetch_from_broadcast_queue_tool = FunctionTool(
    func=fetch_from_broadcast_queue,
    description="Fetches items from the broadcast queue with the specified status for processing or review"
)

update_broadcast_queue_item_tool = FunctionTool(
    func=update_broadcast_queue_item,
    description="Updates the status of an item in the broadcast queue and optionally adds post information"
)

# Fix schema for OpenAI by adding type field
for tool in [fetch_from_broadcast_queue_tool, update_broadcast_queue_item_tool]:
    schema = tool.schema
    schema["type"] = "function" 