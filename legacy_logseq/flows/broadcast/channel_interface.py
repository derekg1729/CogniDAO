"""
Channel interface for BroadcastCogni system

Defines the common interface that all broadcast channel implementations must follow.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple


class BroadcastChannel(ABC):
    """
    Abstract base class for all broadcast channels
    
    All channel implementations must implement these methods.
    """
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the channel's API
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_content(self, content: str) -> Tuple[bool, str]:
        """
        Validate content against channel's requirements
        
        Args:
            content: The content to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def publish(self, content: str) -> Dict[str, Any]:
        """
        Publish content to the channel
        
        Args:
            content: The content to broadcast
            
        Returns:
            dict: Result of publishing attempt
        """
        pass
    
    @abstractmethod
    def get_status(self, post_id: str) -> Dict[str, Any]:
        """
        Get status of a published post
        
        Args:
            post_id: ID of the post to check
            
        Returns:
            dict: Status information
        """
        pass 