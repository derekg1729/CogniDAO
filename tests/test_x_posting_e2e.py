"""
End-to-end test for X posting flow

Tests the entire X posting flow with minimal mocking, using the test broadcast queue.
"""

import os
import sys
import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure parent directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the flow and required classes
from legacy_logseq.flows.broadcast.x_posting_flow import async_x_posting_flow
from legacy_logseq.constants import (
    BROADCAST_QUEUE_TEST_SESSION,
    BROADCAST_QUEUE_TEST_ROOT,
    TEST_MOCK_MEMORY_ROOT,
)


# Test fixture to set up and tear down test data
@pytest.fixture
def setup_test_queue():
    """
    Sets up a test broadcast queue with sample data
    """
    # Create test directories
    state_dir = BROADCAST_QUEUE_TEST_ROOT / "state"
    pages_dir = BROADCAST_QUEUE_TEST_ROOT / "pages"
    log_dir = BROADCAST_QUEUE_TEST_ROOT / "log"

    for directory in [state_dir, pages_dir, log_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Create sample approved items
    items = [
        {
            "queue_id": "test-item-001",
            "content": "This is a test post for the e2e test #testing",
            "source": "test",
            "priority": 1,
            "status": "approved",
            "creation_time": datetime.utcnow().isoformat(),
            "scheduled_time": "asap",
        }
    ]

    # Write to state files
    for item in items:
        queue_id = item["queue_id"]
        state_file = state_dir / f"{queue_id}.json"

        with open(state_file, "w") as f:
            json.dump(item, f, indent=2)

        # Also create a corresponding page file
        page_content = f"""title:: 📨 Pending Broadcast: {queue_id}
tags:: #broadcast_queue #approved #review
type:: {item["source"]}
priority:: {item["priority"]}
status:: approved
created:: {item["creation_time"]}
source:: {item["source"]}
scheduled:: {item["scheduled_time"]}

---

## ✨ Content

"{item["content"]}"

---

## ✅ Approval

- [x] Approved for broadcast
- [ ] Needs revision
- Notes::
"""
        page_file = pages_dir / f"{queue_id}.md"
        with open(page_file, "w") as f:
            f.write(page_content)

    yield

    # Clean up test files
    import shutil

    if BROADCAST_QUEUE_TEST_ROOT.exists():
        shutil.rmtree(BROADCAST_QUEUE_TEST_ROOT)

    # Also clean up test memory bank files
    test_flow_dir = TEST_MOCK_MEMORY_ROOT / "flows" / "broadcast_x_posting_test"
    if test_flow_dir.exists():
        shutil.rmtree(test_flow_dir)


# Mock memory bank initialization to use test paths
class MockMemoryBank:
    def __init__(self, **kwargs):
        # Store original args
        self.original_kwargs = kwargs
        self.context = {}
        self.decisions = []
        self.progress = {}

        # Create test dir structure
        memory_root = TEST_MOCK_MEMORY_ROOT
        memory_root.mkdir(parents=True, exist_ok=True)

        # Always use test project regardless of what's passed in
        project_name = "flows/broadcast_x_posting_test"

        # Use same session ID that was passed
        session_id = kwargs.get("session_id", datetime.utcnow().strftime("%Y%m%d_%H%M%S"))

        # Create project directory
        self.project_dir = memory_root / project_name
        self.project_dir.mkdir(parents=True, exist_ok=True)

        # Create session directory
        self.session_dir = self.project_dir / session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self) -> Path:
        """Get the base directory path for the current session."""
        return self.session_dir

    def write_context(self, context_id, data, format="text"):
        self.context[context_id] = data

    def read_context(self, context_id, format="text"):
        return self.context.get(context_id, "")

    def log_decision(self, data):
        self.decisions.append(data)

    def update_progress(self, data):
        self.progress = data
        # Write progress to file to test
        progress_file = self.session_dir / "progress.json"
        with open(progress_file, "w") as f:
            json.dump(data, f, indent=2)


@pytest.mark.asyncio
async def test_x_posting_flow_e2e(setup_test_queue):
    """
    End-to-end test of the X posting flow using the test broadcast queue

    This test:
    1. Uses real authentication with the X API (validates credentials)
    2. Mocks only the actual tweet creation to avoid rate limits
    3. Validates the complete flow with minimal mocking
    4. Uses the test broadcast queue
    """
    # Set up environment patches to use test broadcast queue and test memory bank
    env_patches = [
        patch(
            "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_ROOT",
            BROADCAST_QUEUE_TEST_ROOT,
        ),
        patch(
            "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_SESSION",
            BROADCAST_QUEUE_TEST_SESSION,
        ),
        patch(
            "legacy_logseq.tools.broadcast_queue_update_tool.BROADCAST_QUEUE_ROOT",
            BROADCAST_QUEUE_TEST_ROOT,
        ),
        patch(
            "legacy_logseq.tools.broadcast_queue_update_tool.BROADCAST_QUEUE_SESSION",
            BROADCAST_QUEUE_TEST_SESSION,
        ),
        # Patch the memory bank class to use our mock that forces test paths
        patch("legacy_logseq.flows.broadcast.x_posting_flow.FileMemoryBank", MockMemoryBank),
    ]

    # Create a mock for the create_tweet method
    mock_create_tweet = MagicMock()
    mock_create_tweet.return_value = type(
        "obj",
        (object,),
        {"data": {"id": "123456789", "text": "This is a test post for the e2e test #testing"}},
    )

    # Patch only the create_tweet method in tweepy.Client to avoid rate limits
    # But still use real authentication to validate credentials
    with patch("tweepy.Client.create_tweet", mock_create_tweet):
        # Apply all environment patches
        for p in env_patches:
            p.start()

        try:
            # Run the flow in non-simulation mode (tests real auth)
            # but with mocked tweet creation
            result = await async_x_posting_flow(
                post_limit=1,
                simulation_mode=False,  # Use real auth but mocked tweet creation
            )

            # Verify the flow completed successfully
            assert result["status"] == "success"
            assert result["simulation_mode"] is False
            assert result["posts_processed"] == 1
            assert result["successful_posts"] == 1

            # Verify the mock was called with the right content
            mock_create_tweet.assert_called_once()
            call_kwargs = mock_create_tweet.call_args.kwargs
            assert "text" in call_kwargs
            assert "This is a test post for the e2e test #testing" == call_kwargs["text"]

            # Verify queue item was updated to "posted" status
            state_file = BROADCAST_QUEUE_TEST_ROOT / "state" / "test-item-001.json"
            assert state_file.exists()

            with open(state_file, "r") as f:
                updated_state = json.load(f)

            assert updated_state["status"] == "posted"
            assert "post_info" in updated_state
            assert updated_state["post_info"]["post_id"] == "123456789"

            # Verify log entry was created
            log_file = BROADCAST_QUEUE_TEST_ROOT / "log" / "broadcast_queue.jsonl"
            assert log_file.exists()

            with open(log_file, "r") as f:
                log_entries = [json.loads(line) for line in f.readlines()]

            # Find status update entries
            status_updates = [
                entry for entry in log_entries if entry.get("action_type") == "status_update"
            ]
            assert len(status_updates) > 0

            # Verify the status update
            latest_update = status_updates[-1]
            assert latest_update["queue_id"] == "test-item-001"
            assert latest_update["previous_status"] == "approved"
            assert latest_update["new_status"] == "posted"
            assert latest_update["has_post_info"] is True

            # Verify memory bank files were created in test location
            test_flow_dir = TEST_MOCK_MEMORY_ROOT / "flows" / "broadcast_x_posting_test"
            assert test_flow_dir.exists()

            # At least one session directory should exist (with timestamp name)
            session_dirs = list(test_flow_dir.glob("*"))
            assert len(session_dirs) > 0

            # Filter out any non-directory items
            session_dirs = [d for d in session_dirs if d.is_dir()]
            assert len(session_dirs) > 0

            # Progress file should exist in the session directory
            progress_file = session_dirs[0] / "progress.json"
            assert progress_file.exists()

            # Verify progress content
            with open(progress_file, "r") as f:
                progress_data = json.load(f)

            assert progress_data["posts_processed"] == 1
            assert progress_data["successful_posts"] == 1

        finally:
            # Stop all patches
            for p in env_patches:
                p.stop()


if __name__ == "__main__":
    # Allow running the test directly
    pytest.main(["-v", __file__])
