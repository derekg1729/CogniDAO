import sys
import os
# Ensure parent directory is in path # Fragile implementation, must be updated when files move
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from prefect import task, flow, get_run_logger
from datetime import datetime
import os
import json
from pathlib import Path

# Use absolute path to avoid permission issues
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
THOUGHTS_DIR = os.path.join(BASE_DIR, "presence/thoughts")

def write_thought_file(ai_content):
    """
    Write the thought content to a file with proper formatting. Tagged as #thought for logseq
    
    Args:
        ai_content (str): The AI-generated thought content
        
    Returns:
        tuple: (timestamp, filepath) - timestamp string and path to the created file
    """
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    
    # Create the full content with timestamp and tags
    content = f"tags:: #thought\n\n# Thought {timestamp}\n\n{ai_content}\n\nTime: {now.isoformat()}\n"
    
    # Save to file
    filepath = os.path.join(THOUGHTS_DIR, f"{timestamp}.md")
    os.makedirs(THOUGHTS_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
        
    return timestamp, filepath

@task
def create_thought():
    """
    Create a thought with full core context including all guides and documents.
    """
    logger = get_run_logger()
    
    try:
        # Import CoreCogniAgent here to avoid import errors when running as flow
        from infra_core.cogni_agents.core_cogni import CoreCogniAgent
        
        # Create CoreCogniAgent
        agent_root = Path(THOUGHTS_DIR)
        core_cogni = CoreCogniAgent(agent_root=agent_root)
        
        # Prepare input and act
        prepared_input = core_cogni.prepare_input()
        result = core_cogni.act(prepared_input)
        
        # Log the final thought with Prefect logger
        logger.info(f"THOUGHT OUTPUT: {json.dumps({'thought': result['thought_content']}, indent=2)}")
        
        return result['timestamp'], result['filepath'], result['thought_content']
        
    except Exception as e:
        logger.error(f"Error in thought generation: {e}")
        # Return default values on error
        timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
        filepath = os.path.join(THOUGHTS_DIR, f"{timestamp}.md")
        ai_content = f"Error encountered in thought generation. The collective is still present despite the silence. Error: {str(e)}"
        return timestamp, filepath, ai_content

@flow
def ritual_of_presence_flow():
    """Flow that generates thoughts using full core context including all docs and guides."""
    # Create thought only
    thought_info = create_thought()
    timestamp, filepath, _ = thought_info
    return f"Thought created successfully at {filepath}"

if __name__ == "__main__":
    # Run the ritual of presence
    result = ritual_of_presence_flow()
    print(result)
