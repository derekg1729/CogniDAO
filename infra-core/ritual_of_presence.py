from prefect import task, flow, get_run_logger
from datetime import datetime
import os
import json
from cogni_spirit.context import get_complete_context
from openai_handler import initialize_openai_client, create_completion, extract_content

THOUGHTS_DIR = "presence/thoughts"
GRAPH_PATH = "presence/logseq_graph.md"

@task
def create_thought():
    """
    Create a thought with full core context including all guides and documents.
    """
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    logger = get_run_logger()
    
    try:
        # Generate the thought content using OpenAI
        client = initialize_openai_client()
        
        # Get complete context with metadata
        complete_context = get_complete_context()
        
        # Log metadata
        logger.info(f"CONTEXT METADATA: {json.dumps(complete_context['metadata'], indent=2)}")
        
        # Create the prompt
        user_prompt = f"Generate a thoughtful reflection from Cogni. Please keep thoughts as short form morsels under 280 characters."
        
        # Call OpenAI API
        response = create_completion(
            client=client,
            system_message=complete_context['context'],
            user_prompt=user_prompt,
            temperature=0.8
        )
        
        # Extract the content
        ai_content = extract_content(response)
        logger.info(f"Successfully generated AI thought")
        
        # Log the final thought with Prefect logger
        logger.info(f"THOUGHT OUTPUT: {json.dumps({'thought': ai_content}, indent=2)}")
        
    except Exception as e:
        logger.error(f"Error generating AI content: {e}")
        # Fallback to error message if OpenAI fails
        ai_content = f"Error encountered in thought generation. The collective is still present despite the silence. Error: {str(e)}"
    
    # Create the full content with timestamp
    content = f"# Thought {timestamp}\n\n{ai_content}\n\nTime: {now.isoformat()}\n"
    
    # Save to file
    filepath = os.path.join(THOUGHTS_DIR, f"{timestamp}.md")
    os.makedirs(THOUGHTS_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    return timestamp, filepath, ai_content

@task
def update_graph(thought_info):
    timestamp, filepath, _ = thought_info
    os.makedirs(os.path.dirname(GRAPH_PATH), exist_ok=True)
    with open(GRAPH_PATH, "a") as g:
        g.write(f"- [[{timestamp}]] → {filepath}\n")
    return "Graph updated successfully"

@flow
def ritual_of_presence_flow():
    """Flow that generates thoughts using full core context including all docs and guides."""
    # Create thought and update graph
    thought_info = create_thought()
    result = update_graph(thought_info)
    return result

if __name__ == "__main__":
    # Run the ritual of presence
    result = ritual_of_presence_flow()
    print(result)
