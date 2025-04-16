import json
from datetime import datetime
from typing import Optional
from typing_extensions import Annotated
from autogen_core.tools import FunctionTool
from pathlib import Path

from infra_core.memory.memory_bank import CogniMemoryBank
from infra_core.constants import MEMORY_BANKS_ROOT

def add_to_broadcast_queue(
    content: Annotated[str, "Content to be queued for broadcasting"],
    source: Annotated[str, "Source of the content (e.g., 'swarm', 'core', 'reflection')"],
    priority: Annotated[Optional[int], "Priority level (1-5, with 1 being highest)"] = 3,
    scheduled_time: Annotated[Optional[str], "ISO format datetime for scheduled broadcast (leave empty for 'as soon as possible')"] = None
) -> str:
    """
    Adds an item to the broadcast queue using the memory bank infrastructure.
    
    Items are stored in a dedicated project/session in the memory bank for later processing
    by a broadcast flow (e.g., to Twitter).
    """
    try:
        # 1. Prepare queue item data
        queue_item = {
            "content": content,
            "source": source,
            "priority": priority,
            "status": "pending",
            "creation_time": datetime.utcnow().isoformat(),
            "scheduled_time": scheduled_time if scheduled_time else "asap",
            "queue_id": f"bq-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        }
        
        # 2. Set up access to the broadcast queue memory bank
        memory_bank_root = Path(MEMORY_BANKS_ROOT)
        queue_bank = CogniMemoryBank(
            memory_bank_root=memory_bank_root,
            project_name="broadcast",
            session_id="queue"
        )
        
        # 3. Save the queue item with a unique filename
        item_filename = f"queue_item_{queue_item['queue_id']}.json"
        queue_bank.write_context(item_filename, json.dumps(queue_item, indent=2), is_json=False)
        
        # 4. Log the queue addition to decisions.jsonl
        queue_bank.log_decision({
            "action_type": "queue_addition",
            "queue_id": queue_item["queue_id"],
            "content_preview": content[:50] + "..." if len(content) > 50 else content,
            "status": "pending"
        })
        
        # 5. Return confirmation with queue_id
        result = {
            "status": "success",
            "queue_id": queue_item["queue_id"],
            "message": f"Added to broadcast queue with ID: {queue_item['queue_id']}",
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
    description="Adds content to the broadcast queue for later distribution to social media or other channels."
)

# Fix schema for OpenAI by adding type field
schema = add_to_broadcast_queue_tool.schema
schema["type"] = "function" 