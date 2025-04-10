"""
GitCogniAgent module

This module provides the GitCogniAgent implementation for reviewing GitHub PRs.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import re
import json
from datetime import datetime

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from infra_core.cogni_agents.base import CogniAgent
from infra_core.cogni_spirit.context import get_core_documents, get_guide_for_task
from infra_core.openai_handler import initialize_openai_client, create_completion, extract_content
from github import Github


class GitCogniAgent(CogniAgent):
    """
    GitCogniAgent implementation for PR review.
    
    This agent is responsible for reviewing GitHub pull requests
    using the git-cogni spirit guide to provide structured feedback.
    """
    
    def __init__(self, agent_root: Path):
        """
        Initialize a new GitCogniAgent.
        
        Args:
            agent_root: Root directory for agent outputs
        """
        super().__init__(
            name="git-cogni",
            spirit_path=Path("infra_core/cogni_spirit/spirits/git-cogni.md"),
            agent_root=agent_root
        )
        self.openai_client = None

    def _initialize_client(self):
        """Initialize OpenAI client if not already initialized."""
        if self.openai_client is None:
            self.openai_client = initialize_openai_client()

    def load_core_context(self):
        """Load core context from charter, manifesto, etc."""
        self.core_context = get_core_documents()

    def parse_pr_url(self, pr_url):
        """
        Parse a GitHub PR URL to extract repository and PR number information.
        
        Args:
            pr_url: GitHub PR URL in format https://github.com/owner/repo/pull/123
            
        Returns:
            dict: PR information with owner, repo, and number
        """
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
        
        return result

    def get_pr_branches(self, pr_info):
        """
        Get the source and target branches for a PR.
        
        Args:
            pr_info: PR information with owner, repo, and number
            
        Returns:
            dict: PR branch information
        """
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
            
        except Exception as e:
            result["error"] = f"Error fetching PR: {str(e)}"
        
        return result

    def get_pr_commits(self, pr_info):
        """
        Get commit information from a PR.
        
        Args:
            pr_info: PR information with owner, repo, and number
            
        Returns:
            dict: PR commit information with success status and commit data
        """
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
            
        except Exception as e:
            result["error"] = f"Error fetching commits: {str(e)}"
        
        return result

    def prepare_pr_data(self, pr_info, branch_info, commit_info):
        """
        Prepare PR data in a structured format for analysis.
        
        Args:
            pr_info: Information about the PR
            branch_info: Branch information
            commit_info: Commit information
            
        Returns:
            dict: Structured PR data
        """
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
        
        return pr_data

    def prepare_input(self, pr_url: str) -> Dict[str, Any]:
        """
        Parse PR info, branch diffs, commits.
        
        Args:
            pr_url: GitHub PR URL to review
            
        Returns:
            Dictionary with prepared PR data
        """
        pr_info = self.parse_pr_url(pr_url)
        branches = self.get_pr_branches(pr_info)
        commits = self.get_pr_commits(pr_info)
        pr_data = self.prepare_pr_data(pr_info, branches, commits)
        return {
            "pr_url": pr_url,
            "pr_info": pr_info,
            "branches": branches,
            "commits": commits,
            "pr_data": pr_data
        }

    def review_pr(self, git_cogni_context, core_context, pr_data):
        """
        Review PR data using staged OpenAI calls for each commit and a final verdict.
        
        Args:
            git_cogni_context: Git-cogni spirit guide context
            core_context: Core documents context
            pr_data: PR data including commit information
            
        Returns:
            dict: Review results with individual commit reviews and final verdict
        """
        # Initialize OpenAI client
        self._initialize_client()
        client = self.openai_client
        
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
        for i, commit in enumerate(commits):
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
        
        # Add to results
        review_results["final_verdict"] = final_verdict
        
        return review_results

    def act(self, prepared_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the full PR review and return structured feedback.
        
        Args:
            prepared_input: Dictionary with prepared PR data
            
        Returns:
            Dictionary with review results
        """
        self._initialize_client()
        
        # Get git-cogni spirit guide context for this specific PR
        pr_info = prepared_input["pr_info"]
        task_description = f"Reviewing PR #{pr_info['number']} in {pr_info['owner']}/{pr_info['repo']}"
        
        git_cogni_context = get_guide_for_task(
            task=task_description,
            guides=["git-cogni"]
        )
        
        # Perform the actual review
        review_results = self.review_pr(
            git_cogni_context=git_cogni_context,
            core_context=self.core_context,
            pr_data=prepared_input["pr_data"]
        )
        
        # Add additional metadata
        review_results["pr_url"] = prepared_input["pr_url"]
        review_results["task_description"] = task_description
        
        return review_results

    def review_and_save(self, pr_url: str) -> Dict[str, Any]:
        """
        Top-level utility: load context, prepare input, act, and save results.
        
        Args:
            pr_url: GitHub PR URL to review
            
        Returns:
            Dictionary with review results
        """
        self.load_core_context()
        input_data = self.prepare_input(pr_url)
        
        if not input_data["pr_info"]["success"]:
            # Handle failure to parse PR URL
            error_result = {
                "error": f"Failed to parse PR URL: {input_data['pr_info']['error']}",
                "pr_url": pr_url
            }
            self.record_action(error_result, subdir="errors")
            return error_result
            
        if not input_data["branches"]["success"]:
            # Handle failure to get branch info
            error_result = {
                "error": f"Failed to get branch info: {input_data['branches']['error']}",
                "pr_url": pr_url
            }
            self.record_action(error_result, subdir="errors")
            return error_result
            
        if not input_data["commits"]["success"]:
            # Handle failure to get commit info
            error_result = {
                "error": f"Failed to get commit info: {input_data['commits']['error']}",
                "pr_url": pr_url
            }
            self.record_action(error_result, subdir="errors")
            return error_result
        
        # All checks passed, proceed with review
        results = self.act(input_data)
        
        # Create a prefix based on the verdict and PR info
        prefix = ""
        if "final_verdict" in results and "pr_info" in results:
            pr_info = results["pr_info"]
            
            # Extract verdict (approve, changes, or comment)
            verdict = "unknown"
            if "APPROVE" in results["final_verdict"]:
                verdict = "approve"
            elif "REQUEST_CHANGES" in results["final_verdict"]:
                verdict = "changes"
            else:
                verdict = "comment"
                
            prefix = f"{pr_info['owner']}_{pr_info['repo']}_{pr_info['number']}_{verdict}_"
        
        # Save the review results using the parent class's record_action method
        review_file = self.record_action(results, subdir="reviews", prefix=prefix)
        
        # Add the file path to the results
        results["review_file"] = str(review_file)
        
        return results 