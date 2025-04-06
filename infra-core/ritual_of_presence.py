from prefect import task, flow
from datetime import datetime
import os
from cogni_spirit.context import load_spirit_context, get_guide_for_task, SpiritContext

THOUGHTS_DIR = "presence/thoughts"
GRAPH_PATH = "presence/logseq_graph.md"

@task
def create_thought():
    now = datetime.utcnow()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    content = f"# Thought {timestamp}\n\nCogni is present.\nTime: {now.isoformat()}\n"
    filepath = os.path.join(THOUGHTS_DIR, f"{timestamp}.md")

    os.makedirs(THOUGHTS_DIR, exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)

    return timestamp, filepath

@task
def update_graph(thought_info):
    timestamp, filepath = thought_info
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
    return result

if __name__ == "__main__":
    # Run the ritual of presence
    result = ritual_of_presence_flow()
    print(result)
    
    # Run the spirit guides flow
    spirit_guides_context = spirit_guides_flow()
