import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Import the update tool
from legacy_logseq.tools.broadcast_queue_update_tool import update_broadcast_queue_status
from legacy_logseq.memory.memory_bank import FileMemoryBank
from infra_core.constants import BROADCAST_QUEUE_TEST_SESSION, BROADCAST_QUEUE_TEST_ROOT

# --- Test Constants ---
TEST_QUEUE_ID = f"test-queue-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


# --- Fixtures ---
@pytest.fixture(scope="function")
def setup_test_queue_env():
    """Create test environment directories and ensure they're clean."""
    # Create test directory structure
    for subdir in ["state", "pages", "log"]:
        test_dir = BROADCAST_QUEUE_TEST_ROOT / subdir
        test_dir.mkdir(parents=True, exist_ok=True)

    # Create a test log file if it doesn't exist
    log_file = BROADCAST_QUEUE_TEST_ROOT / "log" / "broadcast_queue.jsonl"
    if not log_file.exists():
        open(log_file, "w").close()

    # Clean up any existing test files with the current TEST_QUEUE_ID before the test
    state_file = BROADCAST_QUEUE_TEST_ROOT / "state" / f"{TEST_QUEUE_ID}.json"
    md_file = BROADCAST_QUEUE_TEST_ROOT / "pages" / f"{TEST_QUEUE_ID}.md"

    if state_file.exists():
        state_file.unlink()
    if md_file.exists():
        md_file.unlink()

    # Yield to run the test
    yield

    # Clean up after test
    try:
        # Remove test files only for the current test queue ID to avoid affecting other tests
        if state_file.exists():
            state_file.unlink()
        if md_file.exists():
            md_file.unlink()
    except Exception as e:
        print(f"Warning: Cleanup failed: {str(e)}")


@pytest.fixture
def create_test_queue_item():
    """Create a test queue item for testing."""
    # Create state file
    state_data = {
        "queue_id": TEST_QUEUE_ID,
        "content": "This is a test broadcast item created for testing purposes.",
        "source": "test",
        "priority": 3,
        "status": "pending",
        "creation_time": datetime.utcnow().isoformat(),
        "scheduled_time": "asap",
    }

    state_file = BROADCAST_QUEUE_TEST_ROOT / "state" / f"{TEST_QUEUE_ID}.json"
    with open(state_file, "w") as f:
        json.dump(state_data, f, indent=2)

    # Create markdown file
    md_content = f"""title:: 📨 Pending Broadcast: {TEST_QUEUE_ID}
tags:: #broadcast_queue #pending #review #test
type:: test
priority:: 3
status:: pending
created:: {state_data["creation_time"]}
source:: test
scheduled:: asap

---

## ✨ Content

"This is a test broadcast item created for testing purposes."

---

## ✅ Approval

- [ ] Approved for broadcast
- [ ] Needs revision
- Notes::
"""

    md_file = BROADCAST_QUEUE_TEST_ROOT / "pages" / f"{TEST_QUEUE_ID}.md"
    with open(md_file, "w") as f:
        f.write(md_content)

    # Log entry
    log_entry = {
        "timestamp": state_data["creation_time"],
        "action_type": "queue_addition",
        "queue_id": TEST_QUEUE_ID,
        "content_preview": state_data["content"][:50] + "..."
        if len(state_data["content"]) > 50
        else state_data["content"],
        "status": "pending",
    }

    log_file = BROADCAST_QUEUE_TEST_ROOT / "log" / "broadcast_queue.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return {
        "queue_id": TEST_QUEUE_ID,
        "state_file": state_file,
        "md_file": md_file,
        "state_data": state_data,
    }


@pytest.fixture
def custom_update_tool():
    """Return a function that calls the update tool with test session parameters."""

    def _update_broadcast_queue_status(scan_all=False):
        """Wrapper for the update_broadcast_queue_status function using test constants."""
        with (
            patch(
                "legacy_logseq.tools.broadcast_queue_update_tool.BROADCAST_QUEUE_SESSION",
                BROADCAST_QUEUE_TEST_SESSION,
            ),
            patch(
                "legacy_logseq.tools.broadcast_queue_update_tool.BROADCAST_QUEUE_ROOT",
                BROADCAST_QUEUE_TEST_ROOT,
            ),
        ):
            return update_broadcast_queue_status(scan_all=scan_all)

    return _update_broadcast_queue_status


# --- Tests ---
class TestBroadcastQueueUpdate:
    """Test suite for the broadcast queue update tool."""

    def test_no_changes_returns_success_with_no_updates(
        self, setup_test_queue_env, create_test_queue_item, custom_update_tool
    ):
        """Test that running the tool without any changes returns success with no updates."""
        # Run update tool with no changes made to the markdown
        result_json = custom_update_tool()
        result = json.loads(result_json)

        # Assertions
        assert result["status"] == "success"
        assert result["scanned_files"] > 0
        assert len(result["updates"]) == 0

    def test_approval_updates_status_and_logs_changes(
        self, setup_test_queue_env, create_test_queue_item, custom_update_tool
    ):
        """Test that approving an item updates its status and logs the change."""
        queue_data = create_test_queue_item
        md_file = queue_data["md_file"]

        # Read current content
        original_content = md_file.read_text()

        # Update content to mark as approved
        approved_content = original_content.replace(
            "- [ ] Approved for broadcast", "- [x] Approved for broadcast"
        )
        approved_content = approved_content.replace("Notes::", "Notes:: Test approval note")
        md_file.write_text(approved_content)

        # Run update tool
        result_json = custom_update_tool()
        result = json.loads(result_json)

        # Read updated state file
        with open(queue_data["state_file"], "r") as f:
            updated_state = json.load(f)

        # Assertions
        assert result["status"] == "success"
        assert len(result["updates"]) == 1
        assert result["updates"][0]["queue_id"] == TEST_QUEUE_ID
        assert result["updates"][0]["new_status"] == "approved"
        assert result["updates"][0]["has_notes"]

        assert updated_state["status"] == "approved"
        assert "updated_time" in updated_state
        assert "notes" in updated_state
        assert updated_state["notes"] == "Test approval note"

        # Check log file for updates
        log_file = BROADCAST_QUEUE_TEST_ROOT / "log" / "broadcast_queue.jsonl"
        with open(log_file, "r") as f:
            log_entries = f.readlines()

        last_entry = json.loads(log_entries[-1])
        assert last_entry["action_type"] == "status_update"
        assert last_entry["queue_id"] == TEST_QUEUE_ID
        assert last_entry["new_status"] == "approved"
        assert last_entry["has_notes"]

    def test_needs_revision_updates_status(
        self, setup_test_queue_env, create_test_queue_item, custom_update_tool
    ):
        """Test that marking an item as needing revision updates its status correctly."""
        queue_data = create_test_queue_item
        md_file = queue_data["md_file"]

        # Read current content
        original_content = md_file.read_text()

        # Update content to mark as needing revision
        revised_content = original_content.replace("- [ ] Needs revision", "- [x] Needs revision")
        revised_content = revised_content.replace("Notes::", "Notes:: Needs more work")
        md_file.write_text(revised_content)

        # Run update tool
        result_json = custom_update_tool()
        result = json.loads(result_json)

        # Read updated state file
        with open(queue_data["state_file"], "r") as f:
            updated_state = json.load(f)

        # Assertions
        assert result["status"] == "success"
        assert len(result["updates"]) == 1
        assert result["updates"][0]["queue_id"] == TEST_QUEUE_ID
        assert result["updates"][0]["new_status"] == "needs_revision"

        assert updated_state["status"] == "needs_revision"
        assert "notes" in updated_state
        assert updated_state["notes"] == "Needs more work"

    def test_scan_all_processes_non_pending_items(
        self, setup_test_queue_env, create_test_queue_item, custom_update_tool
    ):
        """Test that scan_all=True processes items that are not in pending status."""
        queue_data = create_test_queue_item

        # First, update the state to 'approved' directly
        with open(queue_data["state_file"], "r") as f:
            state_data = json.load(f)

        state_data["status"] = "approved"

        with open(queue_data["state_file"], "w") as f:
            json.dump(state_data, f, indent=2)

        # Now update markdown to indicate revision needed
        md_file = queue_data["md_file"]
        original_content = md_file.read_text()
        revised_content = original_content.replace("- [ ] Needs revision", "- [x] Needs revision")
        md_file.write_text(revised_content)

        # First try without scan_all - should not update
        result_json = custom_update_tool(scan_all=False)
        result = json.loads(result_json)

        # Check that our specific test item wasn't updated
        assert not any(update["queue_id"] == TEST_QUEUE_ID for update in result["updates"])

        # Now try with scan_all=True - should update
        result_json = custom_update_tool(scan_all=True)
        result = json.loads(result_json)

        # Read updated state file
        with open(queue_data["state_file"], "r") as f:
            updated_state = json.load(f)

        # Assertions - check our specific test item
        assert result["status"] == "success"
        test_updates = [
            update for update in result["updates"] if update["queue_id"] == TEST_QUEUE_ID
        ]
        assert len(test_updates) == 1
        assert test_updates[0]["new_status"] == "needs_revision"
        assert updated_state["status"] == "needs_revision"

    @patch("legacy_logseq.memory.memory_bank.FileMemoryBank")
    def test_memory_bank_integration(
        self,
        mock_memory_bank_class,
        setup_test_queue_env,
        create_test_queue_item,
        custom_update_tool,
    ):
        """Test that changes are logged to the memory bank."""
        # Set up mock
        mock_instance = MagicMock(spec=FileMemoryBank)
        mock_memory_bank_class.return_value = mock_instance

        queue_data = create_test_queue_item
        md_file = queue_data["md_file"]

        # Update content to mark as approved
        original_content = md_file.read_text()
        approved_content = original_content.replace(
            "- [ ] Approved for broadcast", "- [x] Approved for broadcast"
        )
        md_file.write_text(approved_content)

        # Run update tool
        with patch(
            "legacy_logseq.tools.broadcast_queue_update_tool.FileMemoryBank", mock_memory_bank_class
        ):
            custom_update_tool()

        # Verify memory bank was used to log decision
        mock_instance.log_decision.assert_called_once()
        log_entry = mock_instance.log_decision.call_args[0][0]
        assert log_entry["action_type"] == "status_update"
        assert log_entry["queue_id"] == TEST_QUEUE_ID
        assert log_entry["new_status"] == "approved"

    def test_error_handling(self, setup_test_queue_env):
        """Test that errors are handled gracefully and returned as JSON."""
        # Create a scenario that will cause an error
        with patch(
            "legacy_logseq.tools.broadcast_queue_update_tool.BROADCAST_QUEUE_ROOT",
            Path("/nonexistent/path"),
        ):
            result_json = update_broadcast_queue_status()

        result = json.loads(result_json)

        # Assertions
        assert result["status"] == "error"
        assert "message" in result
        assert "Failed to update broadcast queue status" in result["message"]
