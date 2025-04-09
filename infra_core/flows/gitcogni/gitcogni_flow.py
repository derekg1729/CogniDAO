import sys, os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prefect import task, flow, get_run_logger
import re
from github import Github

@task
def parse_pr_url(pr_url):
    """
    Parse a GitHub PR URL to extract repository and PR number information.
    
    Args:
        pr_url: GitHub PR URL in format https://github.com/owner/repo/pull/123
        
    Returns:
        dict: PR information with owner, repo, and number
    """
    logger = get_run_logger()
    
    # Initialize result with defaults
    result = {
        "owner": None,
        "repo": None,
        "number": None,
        "success": False,
        "error": None
    }
    
    # Handle empty input
    if not pr_url:
        result["error"] = "No PR URL provided"
        return result
    
    # Parse PR URL using regex
    match = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        result["error"] = f"Invalid GitHub PR URL format: {pr_url}"
        return result
    
    # Extract information
    result["owner"] = match.group(1)
    result["repo"] = match.group(2)
    result["number"] = int(match.group(3))
    result["success"] = True
    
    logger.info(f"Parsed PR URL: {result['owner']}/{result['repo']}#{result['number']}")
    return result

@task
def get_pr_branches(pr_info, use_dummy_data=False):
    """
    Get the source and target branches for a PR.
    
    Args:
        pr_info: PR information with owner, repo, and number
        use_dummy_data: Whether to use dummy data instead of actual API call
        
    Returns:
        dict: PR branch information
    """
    logger = get_run_logger()
    
    # Initialize result
    result = {
        "source_branch": None,
        "target_branch": None,
        "success": False,
        "error": None
    }
    
    # Skip if PR info is invalid
    if not pr_info["success"]:
        result["error"] = f"Invalid PR info: {pr_info['error']}"
        return result
    
    # Use dummy data for testing if requested
    if use_dummy_data:
        logger.info("Using dummy data instead of GitHub API")
        result["source_branch"] = "feature/test-branch"
        result["target_branch"] = "main"
        result["success"] = True
        logger.info(f"PR branches (dummy): {result['source_branch']} → {result['target_branch']}")
        return result
    
    try:
        # Create GitHub client (anonymous is fine for public repos)
        client = Github()
        
        # Get repository and PR
        repo = client.get_repo(f"{pr_info['owner']}/{pr_info['repo']}")
        pr = repo.get_pull(pr_info['number'])
        
        # Extract branch information
        result["source_branch"] = pr.head.ref  # Source branch (PR branch)
        result["target_branch"] = pr.base.ref  # Target branch (where PR will merge)
        result["success"] = True
        
        logger.info(f"PR branches: {result['source_branch']} → {result['target_branch']}")
        
    except Exception as e:
        result["error"] = f"Error fetching PR: {str(e)}"
        logger.error(f"Error: {str(e)}")
    
    return result

@flow(name="gitcogni-review-flow")
def gitcogni_review_flow(pr_url=None, use_dummy_data=False):
    """
    GitCogni PR review flow.
    
    Args:
        pr_url: GitHub PR URL to review
        use_dummy_data: Whether to use dummy data for testing
        
    Returns:
        str: Simple status message
    """
    logger = get_run_logger()
    logger.info("Starting GitCogni PR review flow...")
    
    # Exit early if no PR URL provided
    if not pr_url:
        logger.warning("No PR URL provided")
        return "Error: No PR URL provided"
    
    # Step 1: Parse the PR URL
    pr_info = parse_pr_url(pr_url)
    
    # Exit early if parsing failed
    if not pr_info["success"]:
        logger.error(f"Failed to parse PR URL: {pr_info['error']}")
        return f"Error: {pr_info['error']}"
    
    # Step 2: Get branch information
    branch_info = get_pr_branches(pr_info, use_dummy_data)
    
    # Exit early if branch info retrieval failed
    if not branch_info["success"]:
        logger.error(f"Failed to get branch info: {branch_info['error']}")
        return f"Error: {branch_info['error']}"
    
    # Success! Return the branch information
    message = f"PR #{pr_info['number']} branches: {branch_info['source_branch']} → {branch_info['target_branch']}"
    logger.info(f"Success! {message}")
    
    return message

if __name__ == "__main__":
    # Run with dummy data to avoid GitHub API rate limits or missing PRs
    result = gitcogni_review_flow(
        pr_url="https://github.com/derekg1729/CogniDAO/pull/3 ", 
        use_dummy_data=False
    )
    print(result)
