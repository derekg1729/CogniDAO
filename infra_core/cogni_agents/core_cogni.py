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
from infra_core.cogni_agents.base import BaseCogniMemory


class CoreCogniAgent(CogniAgent):
    """
    CoreCogniAgent implementation for Ritual of Presence.
    
    This agent generates Cogni's thoughts using the memory client
    to access core documents and guides.
    """
    
    def __init__(self, agent_root: Path, memory: BaseCogniMemory, project_root_override: Optional[Path] = None):
        """
        Initialize a new CoreCogniAgent.
        
        Args:
            agent_root: Root directory for agent outputs (thought files)
            memory: The memory bank instance this agent should use.
            project_root_override: Optional override for project root path.
        """
        super().__init__(
            name="core-cogni", # Name is required by base class
            spirit_path=Path("infra_core/cogni_spirit/spirits/cogni-core-spirit.md"), 
            agent_root=agent_root,
            memory=memory, # Pass the memory instance
            project_root_override=project_root_override
        )
        self.openai_client = None
        # self.core_context = None # Base class handles loading core_context
    
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
        
        # Ensure client and core context are loaded (handled by _initialize_client)
        self._initialize_client() 
        
        thought_content = "Default thought if generation fails."
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
            print(f"Error during OpenAI call: {e}") 
        
        # Get current timestamp
        timestamp = datetime.utcnow()
        timestamp_str = timestamp.strftime("%Y-%m-%d-%H-%M")
        
        # Result dictionary to be saved
        result_data = {
            "timestamp": timestamp_str,
            "thought_content": thought_content,
            "prompt_used": prompt, 
            "temperature_used": temperature
        }
        
        # Use record_action from base class to save output and log to memory bank
        # output_path = self.record_action(result_data, prefix="thought_")
        
        # Return result including the file path
        # result_data["filepath"] = str(output_path)
        return result_data
    
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