"""
Tests for the X posting flow

Tests the flow that fetches approved items from the broadcast queue and posts them to X.
"""

import os
import sys
import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

# Ensure parent directory is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import the flow and required classes
from legacy_logseq.flows.broadcast.x_posting_flow import (
    get_approved_posts,
    post_to_x,
    x_posting_flow,
)
from legacy_logseq.flows.broadcast.channel_interface import BroadcastChannel
from legacy_logseq.constants import BROADCAST_QUEUE_TEST_SESSION, BROADCAST_QUEUE_TEST_ROOT


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
            "queue_id": "bq-test001",
            "content": "This is a test post for X #testing",
            "source": "test",
            "priority": 1,
            "status": "approved",
            "creation_time": datetime.utcnow().isoformat(),
            "scheduled_time": "asap",
        },
        {
            "queue_id": "bq-test002",
            "content": "This is another test post that is too long and should fail validation. "
            * 10,
            "source": "test",
            "priority": 2,
            "status": "approved",
            "creation_time": datetime.utcnow().isoformat(),
            "scheduled_time": "asap",
        },
    ]

    # Write to state files
    for item in items:
        queue_id = item["queue_id"]
        state_file = state_dir / f"{queue_id}.json"

        with open(state_file, "w") as f:
            json.dump(item, f, indent=2)

    yield

    # Clean up test files
    import shutil

    if BROADCAST_QUEUE_TEST_ROOT.exists():
        shutil.rmtree(BROADCAST_QUEUE_TEST_ROOT)


# Mock X channel for testing
class MockXChannel(BroadcastChannel):
    """Mock implementation of BroadcastChannel for testing"""

    def __init__(self, simulation_mode=True):
        self.simulation_mode = simulation_mode

    def authenticate(self) -> bool:
        return True

    async def async_authenticate(self) -> bool:
        return True

    def validate_content(self, content: str) -> tuple[bool, str]:
        # Fail validation for long content
        if len(content) > 280:
            return False, "Content exceeds maximum length (280 chars)"
        return True, ""

    def publish(self, content: str) -> dict:
        # Simulate successful post
        return {
            "success": True,
            "id": f"mock-{hash(content) % 1000000000}",
            "text": content,
            "created_at": datetime.utcnow().isoformat(),
            "url": f"https://x.com/cogni/status/mock-{hash(content) % 1000000000}",
        }

    def get_status(self, post_id: str) -> dict:
        return {"exists": True, "status": "active"}


# Tests for get_approved_posts task
@pytest.mark.parametrize("limit,expected_count", [(1, 1), (5, 2)])
def test_get_approved_posts(setup_test_queue, limit, expected_count):
    """Test fetching approved posts from the queue"""
    # Skip until implemented
    pytest.skip("Task not yet implemented in the testing environment")

    # Mock environment variables for testing
    with patch(
        "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_ROOT",
        BROADCAST_QUEUE_TEST_ROOT,
    ):
        with patch(
            "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_SESSION",
            BROADCAST_QUEUE_TEST_SESSION,
        ):
            # Mock logger
            logger = MagicMock()

            # Execute task
            with patch("prefect.get_run_logger", return_value=logger):
                result = get_approved_posts(limit=limit)

                # Check results
                assert len(result) == expected_count
                assert all(item["status"] == "approved" for item in result)
                assert result[0]["queue_id"] == "bq-test001"  # Priority 1 should be first


# Test for post_to_x task
def test_post_to_x(setup_test_queue):
    """Test posting to X and updating item status"""
    # Skip until implemented
    pytest.skip("Task not yet implemented in the testing environment")

    # Create test item
    test_item = {
        "queue_id": "bq-test001",
        "content": "This is a test post for X #testing",
    }

    # Create mock channel
    channel = MockXChannel(simulation_mode=True)

    # Mock environment variables for testing
    with patch(
        "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_ROOT",
        BROADCAST_QUEUE_TEST_ROOT,
    ):
        with patch(
            "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_SESSION",
            BROADCAST_QUEUE_TEST_SESSION,
        ):
            # Mock logger
            logger = MagicMock()

            # Execute task
            with patch("prefect.get_run_logger", return_value=logger):
                result = post_to_x(test_item, channel)

                # Check results
                assert result["success"] is True
                assert "post_id" in result
                assert "post_url" in result
                assert result["queue_id"] == "bq-test001"


# Test for validation failure
def test_post_to_x_validation_failure(setup_test_queue):
    """Test posting with content that fails validation"""
    # Skip until implemented
    pytest.skip("Task not yet implemented in the testing environment")

    # Create test item with long content
    test_item = {
        "queue_id": "bq-test002",
        "content": "This is another test post that is too long and should fail validation. " * 10,
    }

    # Create mock channel
    channel = MockXChannel(simulation_mode=True)

    # Mock environment variables for testing
    with patch(
        "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_ROOT",
        BROADCAST_QUEUE_TEST_ROOT,
    ):
        with patch(
            "legacy_logseq.tools.broadcast_queue_fetch_tool.BROADCAST_QUEUE_SESSION",
            BROADCAST_QUEUE_TEST_SESSION,
        ):
            # Mock logger
            logger = MagicMock()

            # Execute task
            with patch("prefect.get_run_logger", return_value=logger):
                result = post_to_x(test_item, channel)

                # Check results
                assert result["success"] is False
                assert "error" in result
                assert "exceeds maximum length" in result["error"]
                assert result["queue_id"] == "bq-test002"


# Test for complete flow
def test_x_posting_flow(setup_test_queue):
    """Test the complete X posting flow"""
    # Skip until implemented
    pytest.skip("Flow not yet implemented in the testing environment")

    # Mock flow components
    with patch(
        "legacy_logseq.flows.broadcast.x_posting_flow.XChannelAdapter",
        return_value=MockXChannel(simulation_mode=True),
    ):
        with patch(
            "legacy_logseq.flows.broadcast.x_posting_flow.get_approved_posts"
        ) as mock_get_posts:
            with patch("legacy_logseq.flows.broadcast.x_posting_flow.post_to_x") as mock_post:
                # Setup mock data
                mock_get_posts.return_value = [
                    {
                        "queue_id": "bq-test001",
                        "content": "This is a test post for X #testing",
                    }
                ]

                mock_post.return_value = {
                    "success": True,
                    "queue_id": "bq-test001",
                    "post_id": "mock-12345",
                    "post_url": "https://x.com/cogni/status/mock-12345",
                }

                # Mock logger
                logger = MagicMock()

                # Execute flow with simulation mode
                with patch("prefect.get_run_logger", return_value=logger):
                    result = x_posting_flow(post_limit=1, simulation_mode=True)

                    # Check flow results
                    assert result["status"] == "success"
                    assert result["simulation_mode"] is True
                    assert result["posts_processed"] == 1
                    assert result["successful_posts"] == 1


# Test for async flow
@pytest.mark.asyncio
async def test_async_x_posting_flow(setup_test_queue):
    """Test the async X posting flow using Prefect Secret blocks"""
    # Skip until implemented
    pytest.skip("Async flow not yet implemented in the testing environment")

    # Mock flow components and secrets
    with patch(
        "legacy_logseq.flows.broadcast.x_posting_flow.XChannelAdapter",
        return_value=MockXChannel(simulation_mode=True),
    ):
        with patch(
            "legacy_logseq.flows.broadcast.x_posting_flow.get_approved_posts"
        ) as mock_get_posts:
            with patch("legacy_logseq.flows.broadcast.x_posting_flow.post_to_x") as mock_post:
                # Setup mock data
                mock_get_posts.return_value = [
                    {
                        "queue_id": "bq-test001",
                        "content": "This is a test post for X #testing",
                    }
                ]

                mock_post.return_value = {
                    "success": True,
                    "queue_id": "bq-test001",
                    "post_id": "mock-12345",
                    "post_url": "https://x.com/cogni/status/mock-12345",
                }

                # Mock logger
                logger = MagicMock()

                # Execute async flow with simulation mode
                from legacy_logseq.flows.broadcast.x_posting_flow import async_x_posting_flow

                with patch("prefect.get_run_logger", return_value=logger):
                    result = await async_x_posting_flow(post_limit=1, simulation_mode=True)

                    # Check flow results
                    assert result["status"] == "success"
                    assert result["simulation_mode"] is True
                    assert result["posts_processed"] == 1
                    assert result["successful_posts"] == 1
