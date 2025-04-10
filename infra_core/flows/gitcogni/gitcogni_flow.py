import sys, os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prefect import task, flow, get_run_logger
from pathlib import Path
import json
from cogni_agents.git_cogni.git_cogni import GitCogniAgent

@flow(name="gitcogni-review-flow")
def gitcogni_review_flow(pr_url=None):
    """
    GitCogni PR review flow.
    
    This flow uses the GitCogniAgent to review a GitHub PR
    and save the results to the agent's reviews directory.
    
    Args:
        pr_url: GitHub PR URL to review
        
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
    base_path = Path(__file__).resolve().parent.parent.parent
    agent_root = base_path / "cogni_agents" / "git_cogni"
    agent = GitCogniAgent(agent_root=agent_root, external_logger=logger)
    
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
        review_results = agent.review_and_save(pr_url)
        
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
                logger.info(f"VERDICT SUMMARY: {json.dumps({'verdict': verdict_summary}, indent=2)}")
        
        # Success!
        logger.info(f"PR review completed successfully")
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
        
        if review_results.get("final_verdict"):
            verdict = review_results["final_verdict"]
            # Extract decision using simple string search
            if "APPROVE" in verdict:
                decision = "APPROVE"
            elif "REQUEST_CHANGES" in verdict:
                decision = "REQUEST CHANGES"
            else:
                decision = "COMMENT"
            
            print(f"Final verdict: {decision}")
