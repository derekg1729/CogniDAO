"""
X Posting Flow

A Prefect flow that fetches approved items from the broadcast queue and posts them to X.
"""

import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from prefect import task, flow, get_run_logger

# --- Project Constants Import ---
from legacy_logseq.constants import MEMORY_BANKS_ROOT

# --- Memory Imports ---
from legacy_logseq.memory.memory_bank import FileMemoryBank

# --- Channel Imports ---
from legacy_logseq.flows.broadcast.channel_interface import BroadcastChannel
from legacy_logseq.flows.broadcast.channels.x.x_channel_adapter import XChannelAdapter

# --- Broadcast Queue Tool Imports ---
from legacy_logseq.tools.broadcast_queue_fetch_tool import (
    fetch_from_broadcast_queue,
    update_broadcast_queue_item,
)
from legacy_logseq.tools.broadcast_queue_update_tool import update_broadcast_queue_status
from legacy_logseq.constants import BROADCAST_QUEUE_PROJECT, BROADCAST_QUEUE_SESSION


@flow
def auth_test_flow(credentials_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Test authentication with X API credentials without posting anything

    Args:
        credentials_path: Path to X API credentials file (optional, uses Prefect Secret if None)

    Returns:
        Authentication result
    """
    logger = get_run_logger()
    logger.info("Testing X API authentication")

    # Initialize X channel adapter in non-simulation mode to test real auth
    # But don't actually post anything
    x_channel = XChannelAdapter(credentials_path=credentials_path, simulation_mode=False)

    try:
        # Try to authenticate
        auth_result = x_channel.authenticate()

        if auth_result:
            logger.info("✓ Authentication successful!")
            logger.info(f"Auth result details: {auth_result}")
            return {
                "status": "success",
                "message": "Authentication successful! Your X credentials are working.",
            }
        else:
            logger.error("✗ Authentication failed")
            logger.error(f"Auth result value: {auth_result}")
            return {
                "status": "error",
                "message": "Authentication failed. Check your X credentials.",
            }
    except Exception as e:
        logger.error(f"✗ Authentication error: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        return {"status": "error", "message": f"Authentication error: {str(e)}", "error": str(e)}


@flow
async def async_auth_test_flow() -> Dict[str, Any]:
    """
    Test authentication with X API using Prefect Secret credentials without posting anything

    Returns:
        Authentication result
    """
    logger = get_run_logger()
    logger.info("Testing X API authentication with Prefect Secret block")

    # Initialize X channel adapter in non-simulation mode to test real auth
    # But don't actually post anything
    x_channel = XChannelAdapter(simulation_mode=False)

    try:
        # Try to authenticate using async method with Prefect Secret
        auth_result = await x_channel.async_authenticate()

        if auth_result:
            logger.info("✓ Authentication successful!")
            logger.info(f"Auth result details: {auth_result}")
            return {
                "status": "success",
                "message": "Authentication successful! Your X credentials in Prefect Secret are working.",
            }
        else:
            logger.error("✗ Authentication failed")
            logger.error(f"Auth result value: {auth_result}")
            return {
                "status": "error",
                "message": "Authentication failed. Check your X credentials in the Prefect 'x-credentials' Secret.",
            }
    except Exception as e:
        logger.error(f"✗ Authentication error: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        return {"status": "error", "message": f"Authentication error: {str(e)}", "error": str(e)}


@task
def get_approved_posts(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Fetches approved posts from the broadcast queue

    Args:
        limit: Maximum number of posts to fetch

    Returns:
        List of approved post items
    """
    logger = get_run_logger()
    logger.info(f"Fetching up to {limit} approved posts from broadcast queue")

    # Use the fetch tool to get approved posts
    result_json = fetch_from_broadcast_queue(
        status="approved", limit=limit, sort_by="priority", sort_order="asc"
    )

    # Parse the JSON result
    result = json.loads(result_json)

    if result.get("status") != "success":
        logger.error(f"Failed to fetch approved posts: {result.get('message')}")
        return []

    logger.info(f"Found {result.get('total_items')} approved posts")
    return result.get("items", [])


@task
def post_to_x(post_item: Dict[str, Any], channel: BroadcastChannel) -> Dict[str, Any]:
    """
    Posts content to X and updates the queue item status

    Args:
        post_item: The queue item to post
        channel: The X channel adapter

    Returns:
        Result of the posting operation
    """
    logger = get_run_logger()
    queue_id = post_item.get("queue_id")
    content = post_item.get("content")

    logger.info(f"Posting item {queue_id} to X")

    # Validate content
    is_valid, error_message = channel.validate_content(content)
    if not is_valid:
        logger.error(f"Content validation failed for {queue_id}: {error_message}")

        # Update item status to needs_revision
        update_broadcast_queue_item(
            queue_id=queue_id,
            new_status="needs_revision",
            post_info={"error": error_message, "timestamp": datetime.utcnow().isoformat()},
        )

        return {"success": False, "queue_id": queue_id, "error": error_message}

    # Post to X
    result = channel.publish(content)

    if not result.get("success"):
        logger.error(f"Failed to post {queue_id} to X: {result.get('error')}")

        # Don't update status if there was a temporary error (API rate limits, etc)
        # This allows for retry in the next run

        return {"success": False, "queue_id": queue_id, "error": result.get("error")}

    # Post was successful, update item status to posted
    logger.info(f"Successfully posted {queue_id} to X, updating status")

    update_broadcast_queue_item(
        queue_id=queue_id,
        new_status="posted",
        post_info={
            "post_id": result.get("id"),
            "post_url": result.get("url"),
            "timestamp": result.get("created_at") or datetime.utcnow().isoformat(),
        },
    )

    return {
        "success": True,
        "queue_id": queue_id,
        "post_id": result.get("id"),
        "post_url": result.get("url"),
    }


@task
def update_queue_status() -> Dict[str, Any]:
    """
    Updates broadcast queue items based on approval status in markdown files

    Returns:
        Dictionary with update results
    """
    logger = get_run_logger()
    logger.info("Scanning broadcast queue files for approval status updates")

    # Run the update tool to scan all items
    result_json = update_broadcast_queue_status(scan_all=True)

    # Parse the JSON result
    result = json.loads(result_json)

    if result.get("status") != "success":
        logger.error(f"Failed to update queue status: {result.get('message')}")
    else:
        logger.info(f"Updated {len(result.get('updates', []))} queue items")

        # Log the specific updates
        for update in result.get("updates", []):
            logger.info(f"Updated {update.get('queue_id')} to status: {update.get('new_status')}")

    return result


@task
def filter_already_posted(
    approved_posts: List[Dict[str, Any]], flow_memory_bank: FileMemoryBank
) -> List[Dict[str, Any]]:
    """
    Filters out posts that have already been successfully posted by checking flow history

    Args:
        approved_posts: List of approved posts from the queue
        flow_memory_bank: Memory bank to check for past posts

    Returns:
        Filtered list of posts that haven't been posted yet
    """
    logger = get_run_logger()

    if not approved_posts:
        return []

    # Get post IDs from the current batch
    current_queue_ids = [post.get("queue_id") for post in approved_posts]
    logger.info(f"Found {len(current_queue_ids)} approved posts: {', '.join(current_queue_ids)}")

    # Get project path and broadcast queue state path for checking posted items
    broadcast_queue_state_path = (
        Path(MEMORY_BANKS_ROOT) / BROADCAST_QUEUE_PROJECT / BROADCAST_QUEUE_SESSION / "state"
    )
    flow_progress_path = Path(flow_memory_bank._get_session_path()) / "progress.json"
    already_posted_ids = set()

    # First method: Check items directly in the broadcast queue state files
    try:
        if broadcast_queue_state_path.exists():
            # Find all state files
            state_files = list(broadcast_queue_state_path.glob("*.json"))
            for state_file in state_files:
                try:
                    with open(state_file, "r") as f:
                        state_data = json.load(f)

                    # If this item has already been posted, add it to our filter set
                    if state_data.get("status") == "posted":
                        already_posted_ids.add(state_data.get("queue_id", state_file.stem))
                except Exception as e:
                    logger.warning(f"Could not read state file {state_file}: {e}")

            logger.info(f"Found {len(already_posted_ids)} already posted items from state files")
    except Exception as e:
        logger.warning(f"Could not check broadcast queue state files: {e}")

    # Second method: Also check the flow's progress file for items that were successfully posted
    try:
        if flow_progress_path.exists():
            with open(flow_progress_path, "r") as f:
                progress_data = json.load(f)

            # Handle both array format and single object format
            if isinstance(progress_data, list):
                # Array format
                for entry in progress_data:
                    if isinstance(entry, dict) and "results" in entry:
                        for result in entry.get("results", []):
                            if (
                                isinstance(result, dict)
                                and result.get("success")
                                and result.get("queue_id")
                            ):
                                already_posted_ids.add(result.get("queue_id"))
            elif isinstance(progress_data, dict) and "results" in progress_data:
                # Single object format
                for result in progress_data.get("results", []):
                    if (
                        isinstance(result, dict)
                        and result.get("success")
                        and result.get("queue_id")
                    ):
                        already_posted_ids.add(result.get("queue_id"))

            logger.info(
                f"Found a total of {len(already_posted_ids)} previously posted items (including from progress history)"
            )
    except Exception as e:
        logger.warning(f"Could not read flow progress file: {e}")

    # Filter out posts that have already been successfully processed
    filtered_posts = [
        post for post in approved_posts if post.get("queue_id") not in already_posted_ids
    ]

    skipped_ids = set(current_queue_ids) - {post.get("queue_id") for post in filtered_posts}
    if skipped_ids:
        logger.info(f"Skipping {len(skipped_ids)} already posted items: {', '.join(skipped_ids)}")

    if filtered_posts:
        logger.info(f"Processing {len(filtered_posts)} new approved posts")
    else:
        logger.info("No new approved posts to process")

    return filtered_posts


@flow
def x_posting_flow(
    post_limit: int = 5, credentials_path: Optional[str] = None, simulation_mode: bool = True
) -> Dict[str, Any]:
    """
    Flow for posting approved items from the broadcast queue to X

    Args:
        post_limit: Maximum number of posts to process in this run
        credentials_path: Path to X API credentials (optional)
        simulation_mode: If True, simulates posting instead of actual API calls

    Returns:
        Summary of posting results
    """
    logger = get_run_logger()
    logger.info(
        f"Starting X posting flow (simulation_mode={simulation_mode}) with limit {post_limit}"
    )

    # Initialize X channel adapter
    x_channel = XChannelAdapter(credentials_path=credentials_path, simulation_mode=simulation_mode)

    # Authenticate with X
    auth_result = x_channel.authenticate()
    if not auth_result:
        logger.error("X authentication failed")
        logger.error(f"Auth result value: {auth_result}")
        return {"status": "error", "message": "X authentication failed"}

    logger.info("X authentication successful")
    logger.info(f"Auth result details: {auth_result}")

    # Initialize memory bank for flow state tracking
    flow_project_name = "broadcast_x_posting"

    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)

    flow_memory_bank = FileMemoryBank(
        memory_bank_root=memory_root,
        project_name=f"{BROADCAST_QUEUE_PROJECT}",
        session_id=f"{BROADCAST_QUEUE_SESSION}",  # Use fixed session ID for unified memory
    )

    # Step 1: Update queue status from markdown files
    update_queue_status()

    # Step 2: Get approved posts
    approved_posts = get_approved_posts(limit=post_limit)

    if not approved_posts:
        logger.info("No approved posts found")
        return {
            "status": "success",
            "posts_processed": 0,
            "successful_posts": 0,
            "message": "No approved posts found",
        }

    # Filter out already posted items
    filtered_posts = filter_already_posted(
        approved_posts=approved_posts, flow_memory_bank=flow_memory_bank
    )

    # Process each post
    results = []
    successful_posts = 0

    for post_item in filtered_posts:
        result = post_to_x(post_item=post_item, channel=x_channel)
        results.append(result)

        if result.get("success"):
            successful_posts += 1

    # Log overall results
    logger.info(f"Posted {successful_posts}/{len(filtered_posts)} items to X")

    # Update flow progress
    flow_memory_bank.update_progress(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "posts_processed": len(filtered_posts),
            "successful_posts": successful_posts,
            "results": results,
        }
    )

    logger.info(f"Progress updated in unified memory bank: flows/{flow_project_name}/main")

    # Return summary
    return {
        "status": "success",
        "simulation_mode": simulation_mode,
        "posts_processed": len(filtered_posts),
        "successful_posts": successful_posts,
        "results": results,
        "message": f"Posted {successful_posts}/{len(filtered_posts)} items to X",
    }


@flow
async def async_x_posting_flow(
    post_limit: int = 5, simulation_mode: bool = False
) -> Dict[str, Any]:
    """
    Asynchronous flow for posting approved items from the broadcast queue to X
    Uses Prefect Secret blocks for API credentials

    Args:
        post_limit: Maximum number of posts to process in this run
        simulation_mode: If True, simulates posting instead of actual API calls

    Returns:
        Summary of posting results
    """
    logger = get_run_logger()
    logger.info(
        f"Starting async X posting flow (simulation_mode={simulation_mode}) with limit {post_limit}"
    )

    # Initialize X channel adapter
    x_channel = XChannelAdapter(simulation_mode=simulation_mode)

    # Authenticate with X using async method
    auth_result = await x_channel.async_authenticate()
    if not auth_result:
        logger.error("X authentication failed")
        logger.error(f"Auth result value: {auth_result}")
        return {"status": "error", "message": "X authentication failed"}

    logger.info("X authentication successful")
    logger.info(f"Auth result details: {auth_result}")

    # Initialize memory bank for flow state tracking (for async flow)
    flow_project_name = "broadcast_x_posting"

    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)

    flow_memory_bank = FileMemoryBank(
        memory_bank_root=memory_root,
        project_name=f"flows/{flow_project_name}",
        session_id="main",  # Use fixed session ID for unified memory
    )

    # Step 1: Update queue status from markdown files
    update_queue_status()

    # Step 2: Get approved posts
    approved_posts = get_approved_posts(limit=post_limit)

    if not approved_posts:
        logger.info("No approved posts found")
        return {
            "status": "success",
            "posts_processed": 0,
            "successful_posts": 0,
            "message": "No approved posts found",
        }

    # Filter out already posted items
    filtered_posts = filter_already_posted(
        approved_posts=approved_posts, flow_memory_bank=flow_memory_bank
    )

    # Process each post
    results = []
    successful_posts = 0

    for post_item in filtered_posts:
        result = post_to_x(post_item=post_item, channel=x_channel)
        results.append(result)

        if result.get("success"):
            successful_posts += 1

    # Log overall results
    logger.info(f"Posted {successful_posts}/{len(filtered_posts)} items to X")

    # Update flow progress
    flow_memory_bank.update_progress(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "posts_processed": len(filtered_posts),
            "successful_posts": successful_posts,
            "results": results,
        }
    )

    logger.info(f"Progress updated in unified memory bank: flows/{flow_project_name}/main")

    # Return summary
    return {
        "status": "success",
        "simulation_mode": simulation_mode,
        "posts_processed": len(filtered_posts),
        "successful_posts": successful_posts,
        "results": results,
        "message": f"Posted {successful_posts}/{len(filtered_posts)} items to X",
    }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="X Posting Flow")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of posts to process")
    parser.add_argument("--credentials", type=str, help="Path to X API credentials file")
    parser.add_argument("--live", action="store_true", help="Run in live mode (not simulation)")
    parser.add_argument(
        "--async",
        dest="async_mode",
        action="store_true",
        help="Run in async mode with Prefect Secret blocks",
    )
    parser.add_argument(
        "--auth-only", action="store_true", help="Test authentication only, without posting"
    )
    args = parser.parse_args()

    # Run the appropriate flow
    if args.auth_only:
        if args.async_mode:
            import asyncio

            result = asyncio.run(async_auth_test_flow())
        else:
            result = auth_test_flow(credentials_path=args.credentials)
    elif args.async_mode:
        # For async flow, we need to use asyncio
        import asyncio

        result = asyncio.run(
            async_x_posting_flow(post_limit=args.limit, simulation_mode=not args.live)
        )
    else:
        # Run the synchronous flow
        result = x_posting_flow(
            post_limit=args.limit, credentials_path=args.credentials, simulation_mode=not args.live
        )

    # Print the result
    print(json.dumps(result, indent=2))
