import sys, os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prefect import task, flow, get_run_logger
import re
from github import Github
import json
from datetime import datetime
from cogni_spirit.context import get_core_documents, get_guide_for_task

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
def get_pr_branches(pr_info):
    """
    Get the source and target branches for a PR.
    
    Args:
        pr_info: PR information with owner, repo, and number
        
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

@task
def get_pr_commits(pr_info):
    """
    Get commit information from a PR.
    
    Args:
        pr_info: PR information with owner, repo, and number
        
    Returns:
        dict: PR commit information with success status and commit data
    """
    logger = get_run_logger()
    
    # Initialize result
    result = {
        "commits": [],
        "success": False,
        "error": None
    }
    
    # Skip if PR info is invalid
    if not pr_info["success"]:
        result["error"] = f"Invalid PR info: {pr_info['error']}"
        return result
    
    try:
        # Create GitHub client (anonymous is fine for public repos)
        client = Github()
        
        # Get repository and PR
        repo = client.get_repo(f"{pr_info['owner']}/{pr_info['repo']}")
        pr = repo.get_pull(pr_info['number'])
        
        # Get commits from PR
        commits = list(pr.get_commits())
        logger.info(f"Found {len(commits)} commits in PR")
        
        # Process each commit
        for commit in commits:
            # Get the commit object for additional details
            full_commit = repo.get_commit(commit.sha)
            
            # Clean up file data by removing unnecessary URL fields but keeping important metadata
            files = []
            for file_data in full_commit.raw_data.get("files", []):
                # Create a cleaned version of the file data
                # Keep all fields except explicitly excluded URL fields
                cleaned_file = {}
                
                # Excluding URL related fields. currently, agent will not be processing them, so they are a waste of tokens
                excluded_fields = ["blob_url", "raw_url", "contents_url"]
                
                # Copy all fields except excluded ones
                for key, value in file_data.items():
                    if key not in excluded_fields:
                        cleaned_file[key] = value
                
                files.append(cleaned_file)
                
            # Calculate total diff size (length of all file patches combined)
            total_diff_length = sum(len(file.get("patch", "")) for file in files if "patch" in file)
            
            # Extract commit information
            commit_data = {
                "sha": commit.sha,
                "short_sha": commit.sha[:7],  # First 7 characters of SHA
                "message": commit.commit.message,
                "author": commit.commit.author.name,
                "date": commit.commit.author.date.isoformat(),
                "files": files,
                "files_count": len(files),
                "diff_length": total_diff_length
            }
            
            result["commits"].append(commit_data)
        
        result["success"] = True
        logger.info(f"Successfully retrieved {len(result['commits'])} commits")
        
    except Exception as e:
        result["error"] = f"Error fetching commits: {str(e)}"
        logger.error(f"Error: {str(e)}")
    
    return result

@task
def prepare_pr_data(pr_info, branch_info, commit_info):
    """
    Prepare PR data in a structured format for analysis.
    
    Args:
        pr_info: Information about the PR
        branch_info: Branch information
        commit_info: Commit information
        
    Returns:
        dict: Structured PR data
    """
    logger = get_run_logger()
    
    # Combine all data
    pr_data = {
        "pr_info": pr_info,
        "branch_info": branch_info,
        "commit_info": commit_info,
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "commit_count": len(commit_info["commits"]) if commit_info["success"] else 0
        }
    }
    
    logger.info(f"Prepared PR data structure with {pr_data['metadata']['commit_count']} commits")
    return pr_data

@flow(name="gitcogni-review-flow")
def gitcogni_review_flow(pr_url=None):
    """
    GitCogni PR review flow.
    
    Args:
        pr_url: GitHub PR URL to review
        
    Returns:
        tuple: (status message, PR data structure)
    """
    logger = get_run_logger()
    logger.info("Starting GitCogni PR review flow...")
    
    # Exit early if no PR URL provided
    if not pr_url:
        logger.warning("No PR URL provided")
        return "Error: No PR URL provided", None
    
    # Step 1: Parse the PR URL
    pr_info = parse_pr_url(pr_url)
    
    # Exit early if parsing failed
    if not pr_info["success"]:
        logger.error(f"Failed to parse PR URL: {pr_info['error']}")
        return f"Error: {pr_info['error']}", None
    
    # Step 2: Get branch information
    branch_info = get_pr_branches(pr_info)
    
    # Exit early if branch info retrieval failed
    if not branch_info["success"]:
        logger.error(f"Failed to get branch info: {branch_info['error']}")
        return f"Error: {branch_info['error']}", None
    
    # Step 3: Get commit information
    commit_info = get_pr_commits(pr_info)
    
    # Exit early if commit info retrieval failed
    if not commit_info["success"]:
        logger.error(f"Failed to get commit info: {commit_info['error']}")
        return f"Error: {commit_info['error']}", None
    
    # Step 4: Prepare PR data structure
    pr_data = prepare_pr_data(pr_info, branch_info, commit_info)
    
    # Step 5: Retrieve context from context.py
    logger.info("Retrieving context for GitCogni review...")
    
    # Get core context
    core_context = get_core_documents()
    logger.info(f"CONTEXT METADATA: {json.dumps(core_context['metadata'], indent=2)}")
    
    # Get git-cogni spirit guide
    task_description = f"Reviewing PR #{pr_info['number']} in {pr_info['owner']}/{pr_info['repo']}"
    git_cogni_context = get_guide_for_task(
        task=task_description,
        guides=["git-cogni"]
    )
    
    # Create metadata about the git-cogni content for logging
    git_cogni_metadata = {
        "spirit_guide": "git-cogni",
        "task_description": task_description,
        "content_length": len(git_cogni_context["content"]) if isinstance(git_cogni_context, dict) and "content" in git_cogni_context else 0
    }
    logger.info(f"SPIRIT GUIDE METADATA: {json.dumps(git_cogni_metadata, indent=2)}")
    
    # Success! Return the branch and commit information
    message = f"PR #{pr_info['number']} branches: {branch_info['source_branch']} → {branch_info['target_branch']}"
    logger.info(f"Success! {message}")
    logger.info(f"Found {len(commit_info['commits'])} commits")

    # TODO: Ready for a AI Model call!
    
    # Print commit information with enhanced metadata
    for i, commit in enumerate(commit_info['commits']):
        logger.info(
            f"Commit {i+1}: {commit['short_sha']} - "
            f"{commit['files_count']} files changed ({commit['diff_length']} chars) - "
            f"{commit['message']}"
        )
    
    return message, pr_data

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        # Use PR URL from command line
        pr_url = sys.argv[1]
    else:
        # No URL provided - this will return an error
        pr_url = None
    
    message, pr_data = gitcogni_review_flow(pr_url=pr_url)
    print(message)
    
    # If we have data, show summary
    if pr_data:
        print(f"Collected data for {pr_data['metadata']['commit_count']} commits")
        
        # Find and display any renamed files
        renamed_files = []
        for commit in pr_data['commit_info']['commits']:
            for file in commit['files']:
                if 'previous_filename' in file:
                    renamed_files.append(f"{file['previous_filename']} -> {file['filename']}")
        
        if renamed_files:
            print(f"Found {len(renamed_files)} renamed files:")
            for rename in renamed_files[:5]:  # Show first 5 renames
                print(f"  {rename}")
            if len(renamed_files) > 5:
                print(f"  ... and {len(renamed_files) - 5} more")
