import json
import re
from pathlib import Path
from datetime import datetime
from typing_extensions import Annotated
from autogen_core.tools import FunctionTool

from infra_core.memory.memory_bank import CogniMemoryBank
from infra_core.constants import MEMORY_BANKS_ROOT

def update_broadcast_queue_status(
    scan_all: Annotated[bool, "Whether to scan all items or just pending ones"] = False
) -> str:
    """
    Scans the broadcast queue markdown files for approval decisions and updates JSON state accordingly.
    
    This tool:
    1. Reads all markdown files in the pages/ directory
    2. Checks for approval or revision decisions
    3. Updates the corresponding JSON state files
    4. Logs changes to the decisions.jsonl and broadcast_queue.jsonl files
    """
    try:
        # Set up memory bank access
        memory_bank_root = Path(MEMORY_BANKS_ROOT)
        queue_bank = CogniMemoryBank(
            memory_bank_root=memory_bank_root,
            project_name="broadcast_queue",
            session_id="main"
        )
        
        # Get paths to directories
        pages_dir = memory_bank_root / "broadcast_queue" / "main" / "pages"
        state_dir = memory_bank_root / "broadcast_queue" / "main" / "state"
        log_dir = memory_bank_root / "broadcast_queue" / "main" / "log"
        
        # Ensure directories exist
        pages_dir.mkdir(parents=True, exist_ok=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Find all markdown files in pages directory
        md_files = list(pages_dir.glob('*.md'))
        
        updates = []
        
        # Process each markdown file
        for md_file in md_files:
            queue_id = md_file.stem
            state_file = state_dir / f"{queue_id}.json"
            
            # Skip if state file doesn't exist
            if not state_file.exists():
                continue
                
            # Read current state
            with open(state_file, 'r') as f:
                state_data = json.load(f)
                
            # Skip if not pending and not scanning all
            if not scan_all and state_data.get('status') != 'pending':
                continue
                
            # Read markdown content
            md_content = md_file.read_text()
            
            # Parse for approval/revision status
            approved = re.search(r'- \[x\] Approved for broadcast', md_content) is not None
            needs_revision = re.search(r'- \[x\] Needs revision', md_content) is not None
            
            # Extract notes if available
            notes_match = re.search(r'Notes::(.*?)$', md_content, re.MULTILINE | re.DOTALL)
            notes = notes_match.group(1).strip() if notes_match else ""
            
            # Determine new status
            new_status = state_data.get('status')  # Default to current status
            if approved:
                new_status = 'approved'
            elif needs_revision:
                new_status = 'needs_revision'
                
            # Skip if status hasn't changed
            if new_status == state_data.get('status') and not notes:
                continue
                
            # Update state data
            state_data['status'] = new_status
            state_data['updated_time'] = datetime.utcnow().isoformat()
            if notes:
                state_data['notes'] = notes
                
            # Write updated state back to file
            with open(state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
            # Log the update
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "action_type": "status_update",
                "queue_id": queue_id,
                "previous_status": state_data.get('status', 'unknown'),
                "new_status": new_status,
                "has_notes": bool(notes)
            }
            
            # Add to decisions.jsonl via memory bank
            queue_bank.log_decision(log_entry)
            
            # Also append to broadcast_queue.jsonl
            log_file_path = log_dir / "broadcast_queue.jsonl"
            with open(log_file_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
                
            # Record update for return information
            updates.append({
                "queue_id": queue_id,
                "new_status": new_status,
                "has_notes": bool(notes)
            })
            
        # Return summary of updates
        result = {
            "status": "success",
            "scanned_files": len(md_files),
            "updates": updates,
            "message": f"Scanned {len(md_files)} files, updated {len(updates)} items"
        }
        return json.dumps(result, indent=2)
        
    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"Failed to update broadcast queue status: {str(e)}"
        }
        return json.dumps(error_result, indent=2)

update_broadcast_queue_status_tool = FunctionTool(
    func=update_broadcast_queue_status,
    description="Scans broadcast queue markdown files for approval decisions and updates JSON state accordingly"
)

# Fix schema for OpenAI by adding type field
schema = update_broadcast_queue_status_tool.schema
schema["type"] = "function" 