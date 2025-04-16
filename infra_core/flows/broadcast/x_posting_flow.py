"""
X Posting Flow

A Prefect flow that fetches approved items from the broadcast queue and posts them to X.
"""
import sys
import os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from prefect import task, flow, get_run_logger

# --- Project Constants Import ---
from infra_core.constants import (
    MEMORY_BANKS_ROOT
)

# --- Memory Imports ---
from infra_core.memory.memory_bank import CogniMemoryBank

# --- Channel Imports ---
from infra_core.flows.broadcast.channel_interface import BroadcastChannel
from infra_core.flows.broadcast.channels.x.x_channel_adapter import XChannelAdapter

# --- Broadcast Queue Tool Imports ---
from infra_core.tools.broadcast_queue_fetch_tool import (
    fetch_from_broadcast_queue, 
    update_broadcast_queue_item
)

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
            return {
                "status": "success",
                "message": "Authentication successful! Your X credentials are working."
            }
        else:
            logger.error("✗ Authentication failed")
            return {
                "status": "error",
                "message": "Authentication failed. Check your X credentials."
            }
    except Exception as e:
        logger.error(f"✗ Authentication error: {str(e)}")
        return {
            "status": "error",
            "message": f"Authentication error: {str(e)}",
            "error": str(e)
        }

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
            return {
                "status": "success",
                "message": "Authentication successful! Your X credentials in Prefect Secret are working."
            }
        else:
            logger.error("✗ Authentication failed")
            return {
                "status": "error",
                "message": "Authentication failed. Check your X credentials in the Prefect 'x-credentials' Secret."
            }
    except Exception as e:
        logger.error(f"✗ Authentication error: {str(e)}")
        return {
            "status": "error",
            "message": f"Authentication error: {str(e)}",
            "error": str(e)
        }

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
        status="approved",
        limit=limit,
        sort_by="priority",
        sort_order="asc"
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
            post_info={
                "error": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return {
            "success": False,
            "queue_id": queue_id,
            "error": error_message
        }
    
    # Post to X
    result = channel.publish(content)
    
    if not result.get("success"):
        logger.error(f"Failed to post {queue_id} to X: {result.get('error')}")
        
        # Don't update status if there was a temporary error (API rate limits, etc)
        # This allows for retry in the next run
        
        return {
            "success": False,
            "queue_id": queue_id,
            "error": result.get("error")
        }
    
    # Post was successful, update item status to posted
    logger.info(f"Successfully posted {queue_id} to X, updating status")
    
    update_broadcast_queue_item(
        queue_id=queue_id,
        new_status="posted",
        post_info={
            "post_id": result.get("id"),
            "post_url": result.get("url"),
            "timestamp": result.get("created_at") or datetime.utcnow().isoformat()
        }
    )
    
    return {
        "success": True,
        "queue_id": queue_id,
        "post_id": result.get("id"),
        "post_url": result.get("url")
    }

@flow
def x_posting_flow(
    post_limit: int = 5,
    credentials_path: Optional[str] = None,
    simulation_mode: bool = True
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
    logger.info(f"Starting X posting flow (simulation_mode={simulation_mode}) with limit {post_limit}")
    
    # Initialize X channel adapter
    x_channel = XChannelAdapter(credentials_path=credentials_path, simulation_mode=simulation_mode)
    
    # Authenticate with X
    if not x_channel.authenticate():
        logger.error("X authentication failed")
        return {
            "status": "error",
            "message": "X authentication failed"
        }
    
    logger.info("X authentication successful")
    
    # Initialize memory bank for flow state tracking
    flow_project_name = "broadcast_x_posting"
    flow_session_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)
    
    flow_memory_bank = CogniMemoryBank(
        memory_bank_root=memory_root,
        project_name=f"flows/{flow_project_name}",
        session_id=flow_session_id
    )
    
    # Get approved posts
    approved_posts = get_approved_posts(limit=post_limit)
    
    if not approved_posts:
        logger.info("No approved posts found")
        return {
            "status": "success",
            "posts_processed": 0,
            "successful_posts": 0,
            "message": "No approved posts found"
        }
    
    # Process each post
    results = []
    successful_posts = 0
    
    for post_item in approved_posts:
        result = post_to_x(post_item=post_item, channel=x_channel)
        results.append(result)
        
        if result.get("success"):
            successful_posts += 1
    
    # Log overall results
    logger.info(f"Posted {successful_posts}/{len(approved_posts)} items to X")
    
    # Update flow progress
    flow_memory_bank.update_progress({
        "timestamp": datetime.utcnow().isoformat(),
        "posts_processed": len(approved_posts),
        "successful_posts": successful_posts,
        "results": results
    })
    
    # Return summary
    return {
        "status": "success",
        "simulation_mode": simulation_mode,
        "posts_processed": len(approved_posts),
        "successful_posts": successful_posts,
        "results": results,
        "message": f"Posted {successful_posts}/{len(approved_posts)} items to X"
    }

@flow
async def async_x_posting_flow(
    post_limit: int = 5,
    simulation_mode: bool = False
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
    logger.info(f"Starting async X posting flow (simulation_mode={simulation_mode}) with limit {post_limit}")
    
    # Initialize X channel adapter
    x_channel = XChannelAdapter(simulation_mode=simulation_mode)
    
    # Authenticate with X using async method
    if not await x_channel.async_authenticate():
        logger.error("X authentication failed")
        return {
            "status": "error",
            "message": "X authentication failed"
        }
    
    logger.info("X authentication successful")
    
    # Initialize memory bank for flow state tracking
    flow_project_name = "broadcast_x_posting"
    flow_session_id = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    
    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True)
    
    flow_memory_bank = CogniMemoryBank(
        memory_bank_root=memory_root,
        project_name=f"flows/{flow_project_name}",
        session_id=flow_session_id
    )
    
    # Get approved posts (run synchronously within async flow)
    approved_posts = get_approved_posts(limit=post_limit)
    
    if not approved_posts:
        logger.info("No approved posts found")
        return {
            "status": "success",
            "posts_processed": 0,
            "successful_posts": 0,
            "message": "No approved posts found"
        }
    
    # Process each post
    results = []
    successful_posts = 0
    
    for post_item in approved_posts:
        result = post_to_x(post_item=post_item, channel=x_channel)
        results.append(result)
        
        if result.get("success"):
            successful_posts += 1
    
    # Log overall results
    logger.info(f"Posted {successful_posts}/{len(approved_posts)} items to X")
    
    # Update flow progress
    flow_memory_bank.update_progress({
        "timestamp": datetime.utcnow().isoformat(),
        "posts_processed": len(approved_posts),
        "successful_posts": successful_posts,
        "results": results
    })
    
    # Return summary
    return {
        "status": "success",
        "simulation_mode": simulation_mode,
        "posts_processed": len(approved_posts),
        "successful_posts": successful_posts,
        "results": results,
        "message": f"Posted {successful_posts}/{len(approved_posts)} items to X"
    }

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='X Posting Flow')
    parser.add_argument('--limit', type=int, default=5, help='Maximum number of posts to process')
    parser.add_argument('--credentials', type=str, help='Path to X API credentials file')
    parser.add_argument('--live', action='store_true', help='Run in live mode (not simulation)')
    parser.add_argument('--async', dest='async_mode', action='store_true', help='Run in async mode with Prefect Secret blocks')
    parser.add_argument('--auth-only', action='store_true', help='Test authentication only, without posting')
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
        result = asyncio.run(async_x_posting_flow(
            post_limit=args.limit,
            simulation_mode=not args.live
        ))
    else:
        # Run the synchronous flow
        result = x_posting_flow(
            post_limit=args.limit,
            credentials_path=args.credentials,
            simulation_mode=not args.live
        )
    
    # Print the result
    print(json.dumps(result, indent=2)) 