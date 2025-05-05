import json
from datetime import datetime
from typing import Optional
from typing_extensions import Annotated
from autogen_core.tools import FunctionTool
from pathlib import Path

from infra_core.memory.memory_bank import FileMemoryBank
from infra_core.constants import (
    MEMORY_BANKS_ROOT, 
    BROADCAST_QUEUE_PROJECT, 
    BROADCAST_QUEUE_SESSION,
    BROADCAST_QUEUE_ROOT
)

def add_to_broadcast_queue(
    content: Annotated[str, "Content to be queued for broadcasting"],
    source: Annotated[str, "Source of the content (e.g., 'swarm', 'core', 'reflection')"],
    priority: Annotated[Optional[int], "Priority level (1-5, with 1 being highest)"] = 3,
    scheduled_time: Annotated[Optional[str], "ISO format datetime for scheduled broadcast (leave empty for 'as soon as possible')"] = None
) -> str:
    """
    Adds an item to the broadcast queue with structured state, markdown page, and audit log.
    """
    try:
        timestamp = datetime.utcnow().isoformat()
        queue_id = f"bq-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # 1. Prepare core item data
        queue_item = {
            "queue_id": queue_id,
            "content": content,
            "source": source,
            "priority": priority,
            "status": "pending",
            "creation_time": timestamp,
            "scheduled_time": scheduled_time if scheduled_time else "asap"
        }

        # 2. Set up memory bank using constants
        memory_bank_root = Path(MEMORY_BANKS_ROOT)
        queue_bank = FileMemoryBank(
            memory_bank_root=memory_bank_root,
            project_name=BROADCAST_QUEUE_PROJECT,
            session_id=BROADCAST_QUEUE_SESSION
        )

        # 3. Ensure directories exist
        for subdir in ["state", "pages", "log"]:
            queue_bank_dir = BROADCAST_QUEUE_ROOT / subdir
            queue_bank_dir.mkdir(parents=True, exist_ok=True)

        # 4. Save to state/ as .json
        state_filename = f"state/{queue_id}.json"
        queue_bank.write_context(state_filename, queue_item, is_json=True)

        # 5. Save to pages/ as .md for Logseq approval
        page_content = f"""title:: 📨 Pending Broadcast: {queue_id}
tags:: #broadcast_queue #pending #review
type:: {source}
priority:: {priority}
status:: pending
created:: {timestamp}
source:: {source}
scheduled:: {scheduled_time or 'asap'}

---

## ✨ Content

"{content}"

---

## ✅ Approval

- [ ] Approved for broadcast
- [ ] Needs revision
- Notes::
"""
        page_filename = f"pages/{queue_id}.md"
        queue_bank.write_context(page_filename, page_content, is_json=False)

        # 6. Log to .jsonl audit file in log directory
        log_entry = {
            "timestamp": timestamp,
            "action_type": "queue_addition",
            "queue_id": queue_id,
            "content_preview": content[:50] + "..." if len(content) > 50 else content,
            "status": "pending"
        }
        
        # Use log_decision which writes to decisions.jsonl
        queue_bank.log_decision(log_entry)
        
        # Also write to broadcast_queue.jsonl in the log directory for specialized access
        log_file_path = BROADCAST_QUEUE_ROOT / "log" / "broadcast_queue.jsonl"
        
        # Append to broadcast_queue.jsonl
        with open(log_file_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # 7. Return confirmation
        result = {
            "status": "success",
            "queue_id": queue_id,
            "message": f"Added to broadcast queue with ID: {queue_id}",
            "page_path": str(BROADCAST_QUEUE_ROOT / page_filename)
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"Failed to add to broadcast queue: {str(e)}"
        }
        return json.dumps(error_result, indent=2)

add_to_broadcast_queue_tool = FunctionTool(
    func=add_to_broadcast_queue,
    description="Adds content to the broadcast queue for later distribution to social media or other channels. Creates a human-reviewable markdown file."
)

# Fix schema for OpenAI by adding type field
schema = add_to_broadcast_queue_tool.schema
schema["type"] = "function" 