import sys
import os
import datetime
import json
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
# Restore the check and insertion for project_root
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from prefect import flow, get_run_logger # noqa: E402

# Project-specific imports
from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent # noqa: E402
from infra_core.memory.memory_bank import FileMemoryBank # noqa: E402
from infra_core.constants import MEMORY_BANKS_ROOT # noqa: E402

@flow(name="gitcogni-review-flow")
def gitcogni_review_flow(pr_url=None, test_mode=False):
    """
    GitCogni PR review flow.
    
    This flow uses the GitCogniAgent to review a GitHub PR
    and save the results to the agent's reviews directory.
    
    Args:
        pr_url: GitHub PR URL to review
        test_mode: Whether to clean up created files after successful execution
        
    Returns:
        tuple: (status message, review results)
    """
    logger = get_run_logger()
    logger.info("Starting GitCogni PR review flow...")
    
    # Exit early if no PR URL provided
    if not pr_url:
        logger.warning("No PR URL provided")
        return "Error: No PR URL provided", None
    
    # Initialize GitCogniAgent
    logger.info("Initializing GitCogniAgent...")
    project_root = Path(__file__).resolve().parent.parent.parent.parent # Navigate up to project root
    agent_root = project_root / "infra_core" / "cogni_agents" / "git_cogni" # Define agent_root relative to project root

    # Standardize Memory Bank Creation
    flow_project_name = "gitcogni_reviews"
    memory_root = Path(MEMORY_BANKS_ROOT)
    memory_root.mkdir(parents=True, exist_ok=True) # Ensure root exists

    # Create a memory bank instance for this flow run
    session_id = f"review_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}" # Keep unique session ID
    agent_memory = FileMemoryBank(
        memory_bank_root=memory_root, # Use standardized root
        project_name=f"flows/{flow_project_name}", # Use standardized project name structure
        session_id=session_id
    )

    # Log effective paths
    effective_session_id = agent_memory.session_id
    session_path = agent_memory._get_session_path()
    logger.info(f"Initialized memory for project 'flows/{flow_project_name}', session '{effective_session_id}' at {session_path}")
    
    # Pass memory to the agent
    agent = GitCogniAgent(
        agent_root=agent_root, 
        memory=agent_memory, # Pass the memory instance
        external_logger=logger
    )
    
    if test_mode:
        logger.info("Running in test mode - files will be cleaned up after successful execution")
    
    # Run the review process using the agent
    logger.info(f"Reviewing PR: {pr_url}")
    try:
        # Parse PR info first to provide early logging
        pr_parsed = agent.parse_pr_url(pr_url)
        if pr_parsed["success"]:
            logger.info(f"PR INFO: {json.dumps(pr_parsed, indent=2)}")
        else:
            logger.error(f"Error parsing PR URL: {pr_parsed['error']}")
            return f"Error parsing PR URL: {pr_parsed['error']}", None

        # The review_and_save method handles everything:
        # - Parsing the PR URL
        # - Getting branch and commit information
        # - Loading the core context and spirit guide
        # - Performing the actual review
        # - Saving the results to the agent's reviews directory
        # - Cleaning up files if test_mode is enabled
        review_results = agent.review_and_save(pr_url, test_mode=test_mode)
        
        # Check for errors
        if "error" in review_results:
            error_message = review_results["error"]
            logger.error(f"Error during review: {error_message}")
            return f"Error: {error_message}", None
        
        # Log structured data about the review
        if "commit_reviews" in review_results:
            review_stats = {
                "commits_reviewed": len(review_results["commit_reviews"]),
                "commit_shas": [c["commit_sha"] for c in review_results["commit_reviews"]],
                "review_file": review_results.get("review_file", "Unknown")
            }
            logger.info(f"REVIEW STATS: {json.dumps(review_stats, indent=2)}")
            
            # Log verdict summary if available
            if "final_verdict" in review_results:
                verdict_summary = review_results["final_verdict"][:200] + "..." if len(review_results["final_verdict"]) > 200 else review_results["final_verdict"]
                
                # Use verdict_decision field if available
                decision = review_results.get("verdict_decision", agent.get_verdict_from_text(review_results["final_verdict"]))
                logger.info(f"VERDICT SUMMARY: {json.dumps({'verdict': verdict_summary, 'decision': decision}, indent=2)}")
        
        # Success!
        logger.info("PR review completed successfully")
        message = f"PR reviewed. Details: {review_results.get('review_file', 'See reviews directory')}"
        logger.info(f"Success! {message}")
        
        return message, review_results
        
    except Exception as e:
        error_message = f"Unexpected error during review: {str(e)}"
        logger.error(error_message)
        return error_message, None

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        # Use PR URL from command line
        pr_url = sys.argv[1]
    else:
        # No URL provided - this will return an error
        pr_url = None
    
    message, review_results = gitcogni_review_flow(pr_url=pr_url)
    print(message)
    
    # If we have data, show summary
    if review_results:
        print(f"Review completed with {len(review_results.get('commit_reviews', []))} commits analyzed")
        
        # Use verdict_decision field if available, or get it from the agent helper
        if "verdict_decision" in review_results:
            decision = review_results["verdict_decision"]
        elif review_results.get("final_verdict"):
            # Define agent_root specifically for this CLI context
            agent_root = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent / "cogni_agents" / "git_cogni"
            # We already have project_root and agent_root defined above
            
            # Also need to provide memory here for the agent instance
            memory_root = Path(MEMORY_BANKS_ROOT) # Use constant
            cli_project_name = "gitcogni_cli_helper" # Keep distinct project name
            cli_memory = FileMemoryBank(
                memory_bank_root=memory_root,
                project_name=f"flows/{cli_project_name}", # Use flows/ prefix here too? Let's keep it separate for now.
                session_id="cli_verdict_extraction" # Use a fixed or temp session
            )
            # Pass memory when creating agent for verdict extraction
            agent = GitCogniAgent(agent_root=agent_root, memory=cli_memory) 
            decision = agent.get_verdict_from_text(review_results["final_verdict"])
        else:
            decision = "UNKNOWN"
        
        print(f"Final verdict: {decision}")
