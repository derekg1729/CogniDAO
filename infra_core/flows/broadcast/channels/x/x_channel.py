"""
X Channel implementation for BroadcastCogni

This module handles the integration with X API for broadcasting thoughts.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Import tweepy library for X API integration
import tweepy
from prefect.blocks.system import Secret

class XChannel:
    """
    X channel implementation for the BroadcastCogni system
    """
    
    def __init__(self, credentials_path: Optional[str] = None, simulation_mode: bool = True):
        """
        Initialize the X channel with credentials
        
        Args:
            credentials_path: Path to credentials JSON file (optional)
            simulation_mode: If True, simulates posting instead of actual API calls
        """
        # Set up more verbose logging
        self.logger = logging.getLogger("XChannel")
        
        # Ensure logger is set to debug level for detailed output
        self.logger.setLevel(logging.DEBUG)
        
        # Add a console handler if not already present
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
            
        self.simulation_mode = simulation_mode
        
        # Set default credentials path if not provided
        if not simulation_mode and credentials_path:
            self.logger.info(f"Using credentials from file: {credentials_path}")
            self.credentials_path = credentials_path
            self.credentials_source = "file"
        else:
            self.credentials_path = None
            self.credentials_source = "prefect" if not simulation_mode else "simulation"
        
        self.credentials = None
        self.client = None
        
        self.logger.info(f"Initialized XChannel (simulation_mode={simulation_mode}, credentials_source={self.credentials_source})")
        
    async def _load_prefect_secrets(self) -> Dict[str, str]:
        """
        Load X API credentials from Prefect Secret
        
        Returns:
            dict: Credentials dictionary
        """
        try:
            self.logger.info("Loading X API credentials from Prefect Secret block 'x-credentials'")
            
            # Load single JSON secret containing all credentials
            self.logger.debug("Attempting to load Secret block...")
            x_credentials_block = await Secret.load("x-credentials")
            self.logger.debug("Secret block loaded, retrieving value...")
            x_credentials_value = x_credentials_block.get()
            self.logger.debug(f"Secret value type: {type(x_credentials_value)}")
            
            # Handle different types of secrets
            if isinstance(x_credentials_value, dict):
                # Already a dictionary
                self.logger.info("Using credentials dict from Prefect Secret")
                credentials = x_credentials_value
            else:
                # Try to parse as JSON
                try:
                    self.logger.info("Parsing JSON credentials from Prefect Secret")
                    credentials = json.loads(x_credentials_value)
                except (json.JSONDecodeError, TypeError):
                    self.logger.error("Failed to parse X credentials from Secret value")
                    raise ValueError("Invalid format in x-credentials secret, expected JSON or dict")
            
            # Log credential keys (but not values)
            self.logger.debug(f"Credential keys present: {', '.join(credentials.keys())}")
            
            self.logger.info("Successfully loaded X credentials from Prefect Secret")
            return credentials
            
        except Exception as e:
            self.logger.error(f"Error loading X API credentials from Prefect Secret: {str(e)}")
            self.logger.exception("Detailed traceback:")
            raise
        
    def authenticate(self) -> bool:
        """
        Authenticate with X API using stored credentials
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        if self.simulation_mode:
            self.logger.info("X API client authenticated (simulation mode)")
            return True
            
        try:
            # Determine which credentials source to use
            if self.credentials_source == "file":
                if not os.path.exists(self.credentials_path):
                    self.logger.error(f"Credentials file not found: {self.credentials_path}")
                    return False
                    
                with open(self.credentials_path, 'r') as f:
                    self.credentials = json.load(f)
            else:
                # For Prefect, this will be handled in an async context
                # For synchronous usage, fall back to simulation
                self.logger.warning("Prefect Secret blocks require async context, falling back to simulation mode")
                self.simulation_mode = True
                return True
                
            # Validate credentials
            required_keys = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
            for key in required_keys:
                if key not in self.credentials:
                    self.logger.error(f"Missing required credential: {key}")
                    return False
            
            # Initialize tweepy client
            self.client = tweepy.Client(
                consumer_key=self.credentials["api_key"],
                consumer_secret=self.credentials["api_secret"],
                access_token=self.credentials["access_token"],
                access_token_secret=self.credentials["access_token_secret"]
            )
            
            # Verify credentials
            self.logger.info("Verifying X API credentials")
            user = self.client.get_me()
            if user.data:
                self.logger.info(f"Authenticated as X user: {user.data.username}")
                return True
            else:
                self.logger.error("Failed to verify X credentials")
                return False
            
        except Exception as e:
            self.logger.error(f"Error authenticating with X API: {str(e)}")
            return False
    
    async def async_authenticate(self) -> bool:
        """
        Authenticate with X API using Prefect Secret blocks (async version)
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        if self.simulation_mode:
            self.logger.info("X API client authenticated (simulation mode)")
            return True
            
        try:
            # Load credentials from Prefect Secret block
            self.logger.debug("Starting async authentication process...")
            self.credentials = await self._load_prefect_secrets()
            
            # Validate credentials
            required_keys = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
            for key in required_keys:
                if key not in self.credentials:
                    self.logger.error(f"Missing required credential: {key}")
                    return False
            
            # Initialize tweepy client
            self.logger.debug("Initializing tweepy client with credentials...")
            try:
                self.client = tweepy.Client(
                    consumer_key=self.credentials["api_key"],
                    consumer_secret=self.credentials["api_secret"],
                    access_token=self.credentials["access_token"],
                    access_token_secret=self.credentials["access_token_secret"]
                )
                
                # Skip the get_me() call that's causing rate limit issues
                # Instead, just assume authentication is successful if we got this far
                self.logger.info("X API client initialized successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to initialize tweepy client: {str(e)}")
                self.logger.exception("Tweepy client initialization error:")
                return False
            
        except Exception as e:
            self.logger.error(f"Error in async_authenticate: {str(e)}")
            self.logger.exception("Detailed traceback:")
            return False
            
    def validate_content(self, content: str) -> tuple[bool, str]:
        """
        Validate content meets X requirements (e.g., length)
        
        Args:
            content: The content to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # Validate text length
        if len(content) > 280:
            return False, f"Content exceeds maximum length (280 chars). Current length: {len(content)}"
        
        if len(content) < 1:
            return False, "Content cannot be empty"
            
        return True, ""
            
    def publish(self, content: str) -> Dict[str, Any]:
        """
        Publish content to X
        
        Args:
            content: The content to broadcast
            
        Returns:
            dict: Result of publishing attempt
        """
        # Validate content
        is_valid, error = self.validate_content(content)
        if not is_valid:
            return {
                'success': False,
                'error': error
            }
            
        try:
            # Simulation mode
            if self.simulation_mode:
                self.logger.info(f"[SIMULATION] Would post to X: {content}")
                
                # Simulate successful response
                response = {
                    'success': True,
                    'id': f"mock-{hash(content) % 1000000000}",
                    'text': content,
                    'created_at': datetime.utcnow().isoformat(),
                    'url': f"https://x.com/Cogni_1729/status/mock-{hash(content) % 1000000000}"
                }
                
                return response
            
            # Real API call with tweepy
            if not self.client:
                return {
                    'success': False,
                    'error': "Not authenticated. Call authenticate() first."
                }
                
            # Post tweet using tweepy
            self.logger.info(f"Posting to X: {content}")
            try:
                self.logger.debug("Making API call to create_tweet...")
                tweet = self.client.create_tweet(text=content)
                self.logger.debug(f"API Response: {tweet}")
                
                # Handle tweepy response
                if tweet.data:
                    tweet_id = tweet.data['id']
                    self.logger.info(f"Successfully posted to X with ID: {tweet_id}")
                    
                    # Construct response
                    response = {
                        'success': True,
                        'id': str(tweet_id),
                        'text': content,
                        'created_at': datetime.utcnow().isoformat(),
                        'url': f"https://x.com/Cogni_1729/status/{tweet_id}"
                    }
                    
                    return response
                else:
                    self.logger.error(f"Failed to post to X: Empty response. Full response: {tweet}")
                    return {
                        'success': False,
                        'error': "Failed to post: Empty response from X API"
                    }
            except tweepy.errors.TooManyRequests as e:
                self.logger.error(f"Rate limit exceeded during tweet creation: {str(e)}")
                # Log detailed rate limit information if available
                if hasattr(e, 'response') and e.response is not None:
                    self.logger.error(f"Response status: {e.response.status_code}")
                    self.logger.error(f"Response text: {e.response.text}")
                    # Try to extract rate limit headers
                    if 'x-rate-limit-limit' in e.response.headers:
                        self.logger.error(f"Rate limit: {e.response.headers['x-rate-limit-limit']}")
                    if 'x-rate-limit-remaining' in e.response.headers:
                        self.logger.error(f"Rate limit remaining: {e.response.headers['x-rate-limit-remaining']}")
                    if 'x-rate-limit-reset' in e.response.headers:
                        self.logger.error(f"Rate limit reset: {e.response.headers['x-rate-limit-reset']}")
                return {
                    'success': False,
                    'error': f"Rate limit exceeded: {str(e)}",
                    'retry_after': e.response.headers.get('x-rate-limit-reset', 'unknown') if hasattr(e, 'response') else 'unknown'
                }
            except tweepy.errors.Forbidden as e:
                self.logger.error(f"Forbidden error during tweet creation: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    self.logger.error(f"Response text: {e.response.text}")
                return {
                    'success': False,
                    'error': f"Forbidden: {str(e)}"
                }
            except tweepy.errors.Unauthorized as e:
                self.logger.error(f"Unauthorized error during tweet creation: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    self.logger.error(f"Response text: {e.response.text}")
                return {
                    'success': False,
                    'error': f"Unauthorized: {str(e)}"
                }
            except tweepy.errors.BadRequest as e:
                self.logger.error(f"Bad request during tweet creation: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    self.logger.error(f"Response text: {e.response.text}")
                return {
                    'success': False,
                    'error': f"Bad request: {str(e)}"
                }
            except Exception as e:
                self.logger.error(f"API call error during create_tweet: {str(e)}")
                self.logger.exception("Detailed traceback:")
                return {
                    'success': False,
                    'error': str(e)
                }
            
        except Exception as e:
            self.logger.error(f"Error posting to X: {str(e)}")
            self.logger.exception("Detailed traceback:")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_status(self, post_id: str) -> Dict[str, Any]:
        """
        Get status of a published post
        
        Args:
            post_id: ID of the post to check
            
        Returns:
            dict: Status information
        """
        if self.simulation_mode or post_id.startswith("mock-"):
            # Simulation mode response
            self.logger.info(f"[SIMULATION] Getting status for post: {post_id}")
            return {
                'exists': True,
                'status': 'active'
            }
            
        try:
            if not self.client:
                return {
                    'exists': False,
                    'error': "Not authenticated. Call authenticate() first."
                }
                
            # Get tweet info
            tweet = self.client.get_tweet(id=post_id)
            
            if tweet.data:
                return {
                    'exists': True,
                    'status': 'active',
                    'data': tweet.data
                }
            else:
                return {
                    'exists': False,
                    'status': 'not_found'
                }
                
        except tweepy.errors.NotFound:
            return {
                'exists': False,
                'status': 'not_found'
            }
        except Exception as e:
            self.logger.error(f"Error getting status for post {post_id}: {str(e)}")
            return {
                'exists': False,
                'error': str(e)
            }

# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test the channel
    channel = XChannel(simulation_mode=True)
    if channel.authenticate():
        response = channel.publish("This is a test post from BroadcastCogni")
        print(json.dumps(response, indent=2)) 