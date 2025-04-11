import sys
import os
# Ensure parent directory is in path # Fragile implementation, must be updated when files move
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prefect import task, flow, get_run_logger
from datetime import datetime
import os
import json
from cogni_spirit.context import get_core_documents
from openai_handler import initialize_openai_client, create_completion, extract_content

THOUGHTS_DIR = "../../../presence/thoughts"

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
        # Generate the thought content using OpenAI
        client = initialize_openai_client()
        
        # Get complete context with metadata
        core_context = get_core_documents()
        
        # Log metadata
        logger.info(f"CONTEXT METADATA: {json.dumps(core_context['metadata'], indent=2)}")
        
        # Create the prompt
        user_prompt = "Generate a thoughtful reflection from Cogni. Please keep thoughts as short form morsels under 280 characters."
        
        # Call OpenAI API
        response = create_completion(
            client=client,
            system_message=core_context['context'],
            user_prompt=user_prompt,
            temperature=0.8
        )
        
        # Extract the content
        ai_content = extract_content(response)
        logger.info("Successfully generated AI thought")
        
        # Log the final thought with Prefect logger
        logger.info(f"THOUGHT OUTPUT: {json.dumps({'thought': ai_content}, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error generating AI content: {e}")
        # Fallback to error message if OpenAI fails
        ai_content = f"Error encountered in thought generation. The collective is still present despite the silence. Error: {str(e)}"
    
    # Write the thought to a file
    timestamp, filepath = write_thought_file(ai_content)

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
