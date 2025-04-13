"""
CoreCogniAgent implementation for Ritual of Presence

This agent is responsible for generating Cogni's thoughts,
using core context and memory to provide meaningful reflections.
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

from infra_core.cogni_agents.base import CogniAgent
from infra_core.openai_handler import initialize_openai_client, create_completion, extract_content


class CoreCogniAgent(CogniAgent):
    """
    CoreCogniAgent implementation for Ritual of Presence.
    
    This agent generates Cogni's thoughts using the memory client
    to access core documents and guides.
    """
    
    def __init__(self, agent_root: Path):
        """
        Initialize a new CoreCogniAgent.
        
        Args:
            agent_root: Root directory for agent outputs (thought files)
        """
        super().__init__(
            name="core-cogni",
            spirit_path=Path("infra_core/cogni_spirit/spirits/cogni-core-spirit.md"),
            agent_root=agent_root
        )
        self.openai_client = None
        self.core_context = None
    
    def _initialize_client(self):
        """Initialize OpenAI client if not already initialized."""
        if self.openai_client is None:
            self.openai_client = initialize_openai_client()
        
        # Load core context if not already loaded
        if self.core_context is None:
            self.load_core_context()
    
    def prepare_input(self, prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Prepare inputs for thought generation.
        
        Args:
            prompt: Optional custom prompt for thought generation
                   (default prompt will be used if None)
                   
        Returns:
            Dictionary with prepared inputs
        """
        self._initialize_client()
        
        # Use default prompt if none provided
        if prompt is None:
            prompt = "Generate a thoughtful reflection from Cogni. Please keep thoughts as short form morsels under 280 characters."
        
        return {
            "prompt": prompt,
            "temperature": 0.8
        }
    
    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a thought based on core context.
        
        Args:
            prepared_input: Dictionary with prompt and temperature
            
        Returns:
            Dictionary with the thought content and metadata
        """
        prompt = prepared_input.get("prompt")
        temperature = prepared_input.get("temperature", 0.8)
        
        try:
            # Call OpenAI API with core context
            response = create_completion(
                client=self.openai_client,
                system_message=self.core_context['context'],
                user_prompt=prompt,
                temperature=temperature
            )
            
            # Extract the content
            thought_content = extract_content(response)
            
        except Exception as e:
            # Fallback to error message if generation fails
            thought_content = f"Error encountered in thought generation. The collective is still present despite the silence. Error: {str(e)}"
        
        # Get current timestamp
        timestamp = datetime.utcnow()
        timestamp_str = timestamp.strftime("%Y-%m-%d-%H-%M")
        
        # Construct the formatted content for writing
        formatted_content = (
            f"tags:: #thought\n\n"
            f"# Thought {timestamp_str}\n\n"
            f"{thought_content}\n\n"
            f"Time: {timestamp.isoformat()}\n"
        )
        
        # Define filepath
        filepath = self.agent_root / f"{timestamp_str}.md"
        
        # Write the thought file using memory client
        self.memory_client.write_page(
            filepath=str(filepath),
            content=formatted_content,
            append=False
        )
        
        # Return result
        return {
            "timestamp": timestamp_str,
            "filepath": str(filepath),
            "thought_content": thought_content,
            "formatted_content": formatted_content
        }
    
    def format_output_markdown(self, data: Dict[str, Any]) -> str:
        """
        Format the thought output as markdown.
        
        Args:
            data: Dictionary containing thought data
            
        Returns:
            Formatted markdown string
        """
        return (
            f"# Cogni Thought: {data.get('timestamp', '')}\n\n"
            f"## Content\n\n{data.get('thought_content', '')}\n\n"
            f"## Metadata\n\n"
            f"- **Timestamp**: {data.get('timestamp', '')}\n"
            f"- **File**: {data.get('filepath', '')}\n"
        ) 