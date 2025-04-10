"""
GitCogniAgent module

This module provides the GitCogniAgent implementation for reviewing GitHub PRs.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from cogni_agents.base import CogniAgent
from cogni_spirit.context import get_core_documents, get_guide_for_task
from openai_handler import initialize_openai_client, create_completion, extract_content
from flows.gitcogni.gitcogni_flow import (
    parse_pr_url,
    get_pr_branches,
    get_pr_commits,
    prepare_pr_data,
    git_cogni_review
)


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

    def prepare_input(self, pr_url: str) -> Dict[str, Any]:
        """
        Parse PR info, branch diffs, commits.
        
        Args:
            pr_url: GitHub PR URL to review
            
        Returns:
            Dictionary with prepared PR data
        """
        pr_info = parse_pr_url(pr_url)
        branches = get_pr_branches(pr_info)
        commits = get_pr_commits(pr_info)
        pr_data = prepare_pr_data(pr_info, branches, commits)
        return {
            "pr_url": pr_url,
            "pr_info": pr_info,
            "branches": branches,
            "commits": commits,
            "pr_data": pr_data
        }

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
        review_results = git_cogni_review(
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
        
        # Save review results
        output_path = self.record_action(results, subdir="reviews")
        
        # Create summary for convenience
        summary = {
            "pr_url": pr_url,
            "review_file": str(output_path),
            "commit_count": len(input_data["commits"]["commits"]),
            "review_timestamp": results["timestamp"]
        }
        
        self.record_action(summary, subdir="summaries")
        
        return results 