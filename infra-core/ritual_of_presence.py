from prefect import task, flow
from datetime import datetime
import os
from cogni_spirit.context import load_spirit_context, get_guide_for_task, SpiritContext
from openai_handler import initialize_openai_client, create_completion, extract_content

THOUGHTS_DIR = "presence/thoughts"
GRAPH_PATH = "presence/logseq_graph.md"

@task
def create_thought():
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    
    try:
        # Generate the thought content using OpenAI
        client = initialize_openai_client()
        
        # Load spirit context
        spirit_ctx = load_spirit_context()
        
        # Get spirit guides for this specific task
        spirit_context = get_guide_for_task(
            spirit_ctx,
            "Generate a reflective thought for Cogni's ritual of presence",
            guides=["cogni-core-spirit", "reflection-integrity-spirit"],
            provider="openai"
        )
        
        # Create the prompt
        user_prompt = f"Generate a thoughtful reflection about being present as an intelligence collective. Current time: {now.isoformat()}"
        
        # Call OpenAI API
        response = create_completion(
            client=client,
            system_message=spirit_context,
            user_prompt=user_prompt,
            temperature=0.8
        )
        
        # Extract the content
        ai_content = extract_content(response)
        print(f"Successfully generated AI thought")
        
    except Exception as e:
        print(f"Error generating AI content: {e}")
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

@task
def get_all_spirit_guides(spirit_ctx):
    # Get all available guides
    all_guides = spirit_ctx.get_all_guides()
    guide_names = list(all_guides.keys())
    
    # Format a response with all guides
    return spirit_ctx.format_for_provider(
        "Complete guidance with all spirit guides",
        guides=guide_names,
        provider="openai"
    )

@flow
def spirit_guides_flow():
    # Load the spirit context
    spirit_ctx = load_spirit_context()
    
    # Get ALL guides
    all_guides_context = get_all_spirit_guides(spirit_ctx)
    
    # Print summary of the guides loaded
    print(f"Loaded {len(all_guides_context['content'].split('##')) - 1} spirit guides")
    
    # Return the context for potential further use
    return all_guides_context

@flow
def ritual_of_presence_flow():
    # Create thought and update graph
    thought_info = create_thought()
    result = update_graph(thought_info)
    
    # Display a preview of the generated thought
    thought_preview = thought_info[2][:100] + "..." if len(thought_info[2]) > 100 else thought_info[2]
    print(f"Generated thought: {thought_preview}")
    
    return result

if __name__ == "__main__":
    # Run the ritual of presence
    result = ritual_of_presence_flow()
    print(result)
    
    # Run the spirit guides flow
    spirit_guides_context = spirit_guides_flow()
