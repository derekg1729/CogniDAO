"""
X Channel adapter for BroadcastCogni system

Implements the BroadcastChannel interface for X (Twitter) integration.
"""

import logging
from typing import Dict, Any, Tuple, Optional

from legacy_logseq.flows.broadcast.channel_interface import BroadcastChannel
from legacy_logseq.flows.broadcast.channels.x.x_channel import XChannel


class XChannelAdapter(BroadcastChannel):
    """
    X Channel adapter that implements the BroadcastChannel interface

    Wraps the XChannel implementation to conform to the standard interface.
    """

    def __init__(self, credentials_path: Optional[str] = None, simulation_mode: bool = True):
        """
        Initialize the X channel adapter

        Args:
            credentials_path: Path to credentials JSON file (optional)
            simulation_mode: If True, simulates posting instead of actual API calls
        """
        self.logger = logging.getLogger("XChannelAdapter")
        self.x_channel = XChannel(
            credentials_path=credentials_path, simulation_mode=simulation_mode
        )

    def authenticate(self) -> bool:
        """
        Authenticate with the X API

        Returns:
            bool: True if authentication successful, False otherwise
        """
        self.logger.info("Authenticating with X API")
        return self.x_channel.authenticate()

    async def async_authenticate(self) -> bool:
        """
        Authenticate with the X API using async Prefect Secret blocks

        Returns:
            bool: True if authentication successful, False otherwise
        """
        self.logger.info("Authenticating with X API (async)")
        return await self.x_channel.async_authenticate()

    def validate_content(self, content: str) -> Tuple[bool, str]:
        """
        Validate content against X's requirements

        Args:
            content: The content to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        self.logger.info(f"Validating content for X (length: {len(content)})")
        return self.x_channel.validate_content(content)

    def publish(self, content: str) -> Dict[str, Any]:
        """
        Publish content to X

        Args:
            content: The content to broadcast

        Returns:
            dict: Result of publishing attempt
        """
        self.logger.info(f"Publishing content to X: {content[:50]}...")
        return self.x_channel.publish(content)

    def get_status(self, post_id: str) -> Dict[str, Any]:
        """
        Get status of a published post on X

        Args:
            post_id: ID of the post to check

        Returns:
            dict: Status information
        """
        self.logger.info(f"Checking status of X post: {post_id}")
        return self.x_channel.get_status(post_id)
