import json
import re
from pathlib import Path
import time

# Import the update tool
from infra_core.tools.broadcast_queue_update_tool import update_broadcast_queue_status
from infra_core.constants import MEMORY_BANKS_ROOT

def main():
    print("========= Testing Broadcast Queue Update Tool =========")
    
    # Find the most recent markdown file
    memory_bank_root = Path(MEMORY_BANKS_ROOT)
    pages_dir = memory_bank_root / "broadcast_queue" / "main" / "pages"
    
    if not pages_dir.exists():
        print(f"Error: Pages directory not found at {pages_dir}")
        return
    
    md_files = list(pages_dir.glob("*.md"))
    if not md_files:
        print("No markdown files found in pages directory")
        return
    
    # Get the most recent file
    md_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    most_recent_file = md_files[0]
    print(f"Found most recent markdown file: {most_recent_file}")
    
    # First, reset the file to "pending" state with unchecked boxes
    original_content = most_recent_file.read_text()
    
    # Reset the approval checkboxes and notes
    reset_content = re.sub(r'- \[x\] Approved for broadcast', '- [ ] Approved for broadcast', original_content)
    reset_content = re.sub(r'- \[x\] Needs revision', '- [ ] Needs revision', reset_content)
    reset_content = re.sub(r'Notes::.*?$', 'Notes::', reset_content, flags=re.MULTILINE | re.DOTALL)
    
    # Also reset status in the state file
    queue_id = most_recent_file.stem
    state_file = memory_bank_root / "broadcast_queue" / "main" / "state" / f"{queue_id}.json"
    
    if state_file.exists():
        print("\nResetting state file to pending status...")
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        
        state_data['status'] = 'pending'
        if 'notes' in state_data:
            del state_data['notes']
        if 'updated_time' in state_data:
            del state_data['updated_time']
            
        with open(state_file, 'w') as f:
            json.dump(state_data, f, indent=2)
    
    # Write the reset content back to the file
    most_recent_file.write_text(reset_content)
    print("\nReset markdown file to pending state")
    
    print("\nCurrent markdown content:")
    print("========================")
    print(reset_content)
    
    # === TEST CASE 1: Run without any changes ===
    print("\n\n=== TEST CASE 1: Run without any changes ===")
    print("Running update_broadcast_queue_status tool (expecting no changes)...")
    result = update_broadcast_queue_status()
    
    # Parse and print the result
    result_dict = json.loads(result)
    print("\nTool result:")
    print(json.dumps(result_dict, indent=2))
    
    # === TEST CASE 2: Update the file and run again ===
    print("\n\n=== TEST CASE 2: Update the file and run again ===")
    
    # Modify the content to mark it as approved
    print("Updating markdown file with approval...")
    new_content = reset_content.replace("- [ ] Approved for broadcast", "- [x] Approved for broadcast")
    new_content = new_content.replace("Notes::", "Notes:: This reflection is approved for immediate broadcast")
    
    # Write the updated content back
    most_recent_file.write_text(new_content)
    
    # Wait a moment to ensure file write completes
    time.sleep(0.5)
    
    # Run the update tool again
    print("\nRunning update_broadcast_queue_status tool again (expecting 1 update)...")
    result = update_broadcast_queue_status()
    
    # Parse and print the result
    result_dict = json.loads(result)
    print("\nTool result:")
    print(json.dumps(result_dict, indent=2))
    
    # Verify JSON state was updated
    if state_file.exists():
        with open(state_file, 'r') as f:
            state_data = json.load(f)
        print("\nUpdated JSON state:")
        print(json.dumps(state_data, indent=2))
    else:
        print(f"\nError: State file not found at {state_file}")
    
    # Check log file
    log_file = memory_bank_root / "broadcast_queue" / "main" / "log" / "broadcast_queue.jsonl"
    if log_file.exists():
        print("\nLast entry in broadcast_queue.jsonl:")
        with open(log_file, 'r') as f:
            log_entries = f.readlines()
            if log_entries:
                last_entry = json.loads(log_entries[-1])
                print(json.dumps(last_entry, indent=2))
    else:
        print(f"\nError: Log file not found at {log_file}")

if __name__ == "__main__":
    main() 