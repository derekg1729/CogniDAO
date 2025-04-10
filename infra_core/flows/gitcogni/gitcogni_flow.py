import sys, os
# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prefect import task, flow, get_run_logger
import re
from github import Github
import json
from datetime import datetime
from cogni_spirit.context import get_core_documents, get_guide_for_task
from openai_handler import initialize_openai_client, create_completion, extract_content

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

@task
def git_cogni_review(git_cogni_context, core_context, pr_data):
    """
    Review PR data using staged OpenAI calls for each commit and a final verdict.
    
    Args:
        git_cogni_context: Git-cogni spirit guide context
        core_context: Core documents context
        pr_data: PR data including commit information
        
    Returns:
        dict: Review results with individual commit reviews and final verdict
    """
    logger = get_run_logger()
    logger.info("Starting git-cogni review process...")
    
    # Initialize OpenAI client
    client = initialize_openai_client()
    
    # 1. Extract commit data for review
    commits = pr_data['commit_info']['commits']
    pr_info = pr_data['pr_info']
    branch_info = pr_data['branch_info']
    
    # Create output structure
    review_results = {
        "pr_info": {
            "owner": pr_info['owner'],
            "repo": pr_info['repo'],
            "number": pr_info['number'],
            "source_branch": branch_info['source_branch'],
            "target_branch": branch_info['target_branch']
        },
        "commit_reviews": [],
        "final_verdict": None,
        "timestamp": datetime.now().isoformat()
    }
    
    # 2. Process each commit with individual prompts
    logger.info(f"Starting review of {len(commits)} commits...")
    
    for i, commit in enumerate(commits):
        logger.info(f"Reviewing commit {i+1}/{len(commits)}: {commit['short_sha']}")
        
        # Limit patch sizes to avoid token limits
        limited_files = []
        for file in commit['files']:
            file_copy = file.copy()
            if 'patch' in file_copy:
                file_copy['patch'] = file_copy['patch'][:1500]  # Limit patch size
            limited_files.append(file_copy)
        
        # Create prompt for this commit
        commit_prompt = f"""
        Review this specific commit in isolation:
        
        Commit: {commit['short_sha']}
        Message: {commit['message']}
        Author: {commit['author']}
        Date: {commit['date']}
        Files changed: {commit['files_count']}
        
        Details:
        {json.dumps(limited_files, indent=2)}
        
        Provide a brief, structured review of this commit focusing on:
        1. Code quality and simplicity
        2. Clear alignment between code and commit message
        2. Potential issues
        3. Suggestions for improvement
        4. Rating (1-5 stars)
        
        Format your response in markdown.
        """
        
        # Call OpenAI API for this commit, including git-cogni context on all calls
        response = create_completion(
            client=client,
            system_message=git_cogni_context,
            user_prompt=commit_prompt,
            temperature=0.3,  # Lower temperature for consistency
        )
        
        # Extract content
        commit_review = extract_content(response)
        logger.info(f"Completed review for commit {commit['short_sha']} ({len(commit_review)} chars)")
        
        # Store the review
        review_results["commit_reviews"].append({
            "commit_sha": commit['short_sha'],
            "commit_message": commit['message'],
            "review": commit_review
        })
    
    # 3. Final prompt - create a verdict based on all reviews
    all_reviews = "\n\n".join([
        f"## Commit {item['commit_sha']}: {item['commit_message']}\n{item['review']}"
        for item in review_results["commit_reviews"]
    ])
    
    final_prompt = f"""
    You have reviewed all commits in PR #{pr_info['number']} in {pr_info['owner']}/{pr_info['repo']}.
    Source Branch: {branch_info['source_branch']}
    Target Branch: {branch_info['target_branch']}
    
    Individual commit reviews:
    
    {all_reviews}
    
    Please provide a final verdict on this pull request:
    1. Summarize the overall changes and their purpose
    2. List any consistent issues or concerns found across commits
    3. Provide general recommendations for improvement
    4. Give a final decision: APPROVE, REQUEST_CHANGES, or COMMENT
    
    Format your verdict as markdown with clear sections.
    """
    
    # Call OpenAI for final verdict
    final_response = create_completion(
        client=client,
        system_message=git_cogni_context,
        user_prompt=final_prompt,
        temperature=0.3,
    )
    
    # Extract final verdict
    final_verdict = extract_content(final_response)
    logger.info(f"Completed final verdict ({len(final_verdict)} chars)")
    
    # Add to results
    review_results["final_verdict"] = final_verdict
    
    return review_results

@task
def save_review_to_file(review_results):
    """
    Save PR review results to markdown files.
    
    Args:
        review_results: Review results including commit reviews and verdict
        
    Returns:
        dict: Paths to saved files
    """
    logger = get_run_logger()
    
    # Create file names
    pr_info = review_results["pr_info"]
    base_name = f"review_{pr_info['owner']}_{pr_info['repo']}_{pr_info['number']}"
    verdict_file = f"{base_name}_verdict.md"
    details_file = f"{base_name}_details.md"
    
    # Create verdict markdown
    with open(verdict_file, "w") as f:
        # Write header
        f.write(f"# PR Review: #{pr_info['number']} in {pr_info['owner']}/{pr_info['repo']}\n\n")
        f.write(f"**Source Branch:** {pr_info['source_branch']}\n")
        f.write(f"**Target Branch:** {pr_info['target_branch']}\n")
        f.write(f"**Review Date:** {review_results['timestamp']}\n\n")
        
        # Write final verdict
        f.write("## Final Verdict\n\n")
        f.write(review_results["final_verdict"])
    
    # Create detailed review markdown
    with open(details_file, "w") as f:
        # Write header
        f.write(f"# Detailed PR Review: #{pr_info['number']} in {pr_info['owner']}/{pr_info['repo']}\n\n")
        f.write(f"**Source Branch:** {pr_info['source_branch']}\n")
        f.write(f"**Target Branch:** {pr_info['target_branch']}\n")
        f.write(f"**Review Date:** {review_results['timestamp']}\n\n")
        
        # Write each commit review
        f.write("## Individual Commit Reviews\n\n")
        for item in review_results["commit_reviews"]:
            f.write(f"### Commit {item['commit_sha']}: {item['commit_message']}\n\n")
            f.write(item["review"])
            f.write("\n\n---\n\n")
        
        # Write final verdict
        f.write("## Final Verdict\n\n")
        f.write(review_results["final_verdict"])
    
    logger.info(f"Saved verdict to {verdict_file}")
    logger.info(f"Saved detailed review to {details_file}")
    
    return {
        "verdict_file": verdict_file,
        "details_file": details_file
    }

@flow(name="gitcogni-review-flow")
def gitcogni_review_flow(pr_url=None):
    """
    GitCogni PR review flow.
    
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
    
    # Step 6: Perform the PR review
    logger.info("Starting PR review process...")
    review_results = git_cogni_review(git_cogni_context, core_context, pr_data)
    
    # Step 7: Save review results to files
    logger.info("Saving review results to files...")
    files = save_review_to_file(review_results)
    
    # Success! Return the review results
    message = f"PR #{pr_info['number']} reviewed. Verdict: {files['verdict_file']}, Details: {files['details_file']}"
    logger.info(f"Success! {message}")
    
    return message, review_results

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
