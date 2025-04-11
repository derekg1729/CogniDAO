#!/usr/bin/env python
"""
GitCogniAgent for reviewing PRs
"""

import os
import logging
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

from infra_core.cogni_agents.base import CogniAgent
from infra_core.cogni_spirit.context import get_core_documents, get_guide_for_task
from infra_core.openai_handler import initialize_openai_client, create_completion, extract_content, create_thread, thread_completion
from github import Github

# Setup base logger
logger = logging.getLogger(__name__)

class GitCogniAgent(CogniAgent):
    """
    GitCogniAgent implementation for PR review.
    
    This agent is responsible for reviewing GitHub pull requests
    using the git-cogni spirit guide to provide structured feedback.
    """
    
    def __init__(self, agent_root: Path, external_logger=None):
        """
        Initialize a new GitCogniAgent.
        
        Args:
            agent_root: Root directory for agent outputs
            external_logger: Optional external logger (like Prefect's) to use instead of module logger
        """
        super().__init__(
            name="git-cogni",
            spirit_path=Path("infra_core/cogni_spirit/spirits/git-cogni.md"),
            agent_root=agent_root
        )
        self.openai_client = None
        self.logger = external_logger or logger
        self._instrumented = False
        self.created_files = []  # Track files created by this agent instance
    
    @staticmethod
    def setup_logging(verbose=False):
        """
        Setup logging for GitCogni with structured formatting.
        
        Args:
            verbose: Whether to show verbose logs
            
        Returns:
            logger: Configured logger
        """
        level = logging.INFO
        
        # Create custom formatter that highlights important information
        class HighlightFormatter(logging.Formatter):
            """Custom formatter that highlights JSON data"""
            def format(self, record):
                msg = super().format(record)
                # Check if the message contains JSON data indicators
                if any(marker in msg for marker in ["REVIEW DATA:", "COMMIT STATS:", "VERDICT INPUT STATS:", "VERDICT:", "TOKEN MONITOR"]):
                    # Add emphasis with newlines and asterisks for important data
                    return f"\n*{'*' * 80}\n{msg}\n{'*' * 80}*\n"
                return msg
        
        # Configure root logger with both console handlers
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers to avoid duplicate logs
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create console handler with formatting
        console = logging.StreamHandler()
        console.setLevel(level)
        
        # Standard formatter for regular mode
        formatter = logging.Formatter('%(levelname)-8s | %(message)s')
        console.setFormatter(formatter)
        
        # Create a second handler for highlighted content
        highlight_console = logging.StreamHandler()
        highlight_console.setLevel(logging.INFO)  # Always show important info
        highlight_formatter = HighlightFormatter('%(levelname)-8s | %(message)s')
        highlight_console.setFormatter(highlight_formatter)
        
        # Add handlers to root logger
        root_logger.addHandler(console)
        root_logger.addHandler(highlight_console)
        
        # Suppress excessive logging from libraries
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('github').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('websockets').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('graphviz').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
        
        # If verbose is False, also limit prefect logs
        if not verbose:
            logging.getLogger('prefect').setLevel(logging.WARNING)
        
        # Make sure the agent module logger will use root handlers
        agent_logger = logging.getLogger('infra_core.cogni_agents.git_cogni.git_cogni')
        agent_logger.handlers = []  # Clear any existing handlers
        agent_logger.propagate = True  # Ensure it uses the root logger's handlers
        
        # Return the agent logger for use
        return logging.getLogger('gitcogni')
    
    def monitor_token_usage(self, operation, data):
        """
        Log information about operations with potential token usage.
        
        Args:
            operation: Name of the operation being monitored
            data: Data whose token usage is being monitored
        """
        if isinstance(data, str):
            char_length = len(data)
            word_count = len(data.split())
            self.logger.info(f"TOKEN MONITOR | {operation} | ~{word_count} words, {char_length} chars")
    
    def get_verdict_from_text(self, verdict_text):
        """
        Extract the final decision from verdict text.
        
        Args:
            verdict_text: The full verdict text to analyze
            
        Returns:
            str: Final decision (APPROVE, REQUEST_CHANGES, or COMMENT)
        """
        # Standard decision mapping
        if "APPROVE" in verdict_text:
            return "APPROVE"
        elif "REQUEST_CHANGES" in verdict_text:
            return "REQUEST_CHANGES" 
        else:
            return "COMMENT"

    def _initialize_client(self):
        """Initialize OpenAI client if not already initialized."""
        if self.openai_client is None:
            self.openai_client = initialize_openai_client()
            self.thread_id = None
            self.assistant_id = None

    def _combine_contexts(self, git_context, core_context):
        """Safely combine git_cogni_context and core_context."""
        if not core_context:
            return git_context
        
        # If core_context is a string, combine with git_cogni_context
        if isinstance(core_context, str) and core_context.strip():
            return f"{git_context}\n\n{core_context}"
        
        # If core_context is a dictionary or other object with content
        if core_context:
            try:
                # Try to convert to a string representation if it's not empty
                return f"{git_context}\n\n{json.dumps(core_context, indent=2)}"
            except:
                pass
        
        # Default fallback
        return git_context

    def load_core_context(self):
        """Load core context from charter, manifesto, etc."""
        self.logger.info("Loading core context documents")
        self.core_context = get_core_documents()
        if self.core_context and 'metadata' in self.core_context:
            # Count documents from core_docs dictionary
            metadata = self.core_context['metadata']
            document_count = len(metadata.get('core_docs', {}))
            if 'core_spirit' in metadata:
                document_count += 1
            self.logger.info(f"Loaded {document_count} core context documents")

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
        
        # Always create a new thread and assistant for this PR review
        combined_context = self._combine_contexts(git_cogni_context, core_context)
        self.thread_id, self.assistant_id = create_thread(client, combined_context)
        self.logger.info(f"Created thread {self.thread_id} and assistant {self.assistant_id}")
        
        # 1. Extract commit data for review
        commits = pr_data['commit_info']['commits']
        pr_info = pr_data['pr_info']
        branch_info = pr_data['branch_info']
        
        # Log the PR data for debugging
        self.logger.info(f"REVIEW DATA: {json.dumps({
            'pr_owner': pr_info['owner'],
            'pr_repo': pr_info['repo'],
            'pr_number': pr_info['number'],
            'commit_count': len(commits),
            'source_branch': branch_info['source_branch'],
            'target_branch': branch_info['target_branch']
        }, indent=2)}")
        
        # Create output structure
        review_results = {
            "final_verdict": None,
            "pr_info": {
                "owner": pr_info['owner'],
                "repo": pr_info['repo'],
                "number": pr_info['number'],
                "source_branch": branch_info['source_branch'],
                "target_branch": branch_info['target_branch']
            },
            "commit_reviews": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Monitor input context size
        self.monitor_token_usage("git_cogni_context", git_cogni_context)
        
        # Log PR data stats
        if commits:
            commit_stats = {
                "commit_count": len(commits),
                "total_files": sum(c.get("files_count", 0) for c in commits),
                "total_diff_length": sum(c.get("diff_length", 0) for c in commits)
            }
            self.logger.info(f"REVIEW INPUT STATS: {json.dumps(commit_stats, indent=2)}")
        
        # 2. Process each commit with individual prompts
        for i, commit in enumerate(commits):
            self.logger.info(f"Reviewing commit {i+1}/{len(commits)}: {commit['short_sha']} - {commit['message']}")
            
            # Log file count and diff size for monitoring
            self.logger.info(f"COMMIT STATS: {json.dumps({
                'commit_sha': commit['short_sha'],
                'files_count': commit['files_count'],
                'diff_length': commit['diff_length']
            }, indent=2)}")
            
            # Limit patch sizes to avoid token limits
            limited_files = []
            for file in commit['files']:
                file_copy = file.copy()
                if 'patch' in file_copy:
                    file_copy['patch'] = file_copy['patch'][:500]  # Limit patch size to 500 chars (reduced from 1500)
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
            
            Provide a CONCISE and BRIEF, structured review of this commit focusing on:
            1. Code quality and simplicity
            2. Clear alignment between code and commit message
            2. Potential issues
            3. Suggestions for improvement
            4. Rating (1-5 stars)
            
            Be very concise and specifically actionable. Limit your response to 100 words maximum.
            Format your response in markdown.
            """
            
            # Monitor prompt size
            self.monitor_token_usage(f"commit_prompt_{commit['short_sha']}", commit_prompt)
            
            # Call OpenAI API for this commit using thread
            response = thread_completion(
                client=client,
                thread_id=self.thread_id,
                assistant_id=self.assistant_id,
                user_prompt=commit_prompt
            )
            
            # Extract content
            commit_review = extract_content(response)
            self.logger.info(f"Completed review of commit {commit['short_sha']}")
            
            # Monitor response size
            self.monitor_token_usage(f"commit_review_{commit['short_sha']}", commit_review)
            
            # Add the requested logging for individual commit reviews
            self.logger.info(f"COMMIT REVIEW ({commit['short_sha']}): {json.dumps({'review': commit_review}, indent=2)}")
            
            # Store the review
            review_results["commit_reviews"].append({
                "commit_sha": commit['short_sha'],
                "commit_message": commit['message'],
                "review": commit_review
            })
        
        # 3. Final prompt - create a verdict based on all reviews
        self.logger.info(f"Generating final verdict for PR #{pr_info['number']}")
        all_reviews = "\n\n".join([
            f"## Commit {item['commit_sha']}: {item['commit_message']}\n{item['review']}"
            for item in review_results["commit_reviews"]
        ])
        
        # Log the size of the reviews for debugging token limits
        self.logger.info(f"VERDICT INPUT STATS: {json.dumps({
            'review_count': len(review_results['commit_reviews']),
            'combined_reviews_length': len(all_reviews),
            'average_review_length': int(len(all_reviews) / max(1, len(review_results['commit_reviews'])))
        }, indent=2)}")
        
        # Monitor combined reviews size
        self.monitor_token_usage("combined_reviews", all_reviews)
        
        final_prompt = f"""
        You are GitCogni, the spirit-guided code reviewer for PR #{pr_info['number']} in {pr_info['owner']}/{pr_info['repo']}.

        - This PR should be evaluated as a whole, not as isolated commits. 
        - Your goal is to determine whether the final state of the PR (HEAD) aligns with project goals, core directives, and addresses previous shortcomings—even if some commits were imperfect.
        - You are encouraged to recognize iterative improvement, refactor clarity, and the inclusion of tests—even if fixes came in later commits.

        **Context:**
        - Source Branch: {branch_info['source_branch']}
        - Target Branch: {branch_info['target_branch']}

        **Individual Commit Reviews (for context):**

        {all_reviews}

        ---

        ### Please provide a final verdict on this pull request:

        1. **Overall Summary**  
           - Describe the purpose and scope of the PR as it stands in its final state.
           - Highlight key components, systems touched, and architectural intent.

        2. **Consistent Issues (if any)**  
           - Are there still problems that persist in the final version?
           - If issues from earlier commits were later resolved, acknowledge this explicitly.

        3. **Recommendations for Improvement**  
           - Suggest areas to strengthen, even if the PR is approvable.
           - Be constructive and aligned with long-term maintainability.

        4. **Final Decision**  
           - Choose one: `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`
           - Justify your decision based on the final state of the code and spirit-guided alignment.

        ---

        **Important:** Do not reject a PR solely due to earlier commits if the final state resolves those issues. Prioritize clarity, functionality, and long-term alignment.
        
        Format your verdict as markdown with clear sections.
        """
        
        # Monitor final prompt size
        self.monitor_token_usage("final_prompt", final_prompt)
        
        # Call OpenAI for final verdict using thread
        final_response = thread_completion(
            client=client,
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            user_prompt=final_prompt
        )
        
        # Extract final verdict
        final_verdict = extract_content(final_response)
        
        # Monitor final verdict size
        self.monitor_token_usage("final_verdict", final_verdict)
        
        # Add to results
        review_results["final_verdict"] = final_verdict
        
        # Add the verdict decision to results
        review_results["verdict_decision"] = self.get_verdict_from_text(final_verdict)
        
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

    def review_and_save(self, pr_url: str, test_mode: bool = False) -> Dict[str, Any]:
        """
        Top-level utility: load context, prepare input, act, and save results.
        
        Args:
            pr_url: GitHub PR URL to review
            test_mode: Whether to clean up files after successful execution
            
        Returns:
            Dictionary with review results
        """
        self.logger.info(f"Starting review for PR: {pr_url}")
        self.load_core_context()
        
        self.logger.info("Preparing input data")
        input_data = self.prepare_input(pr_url)
        
        if not input_data["pr_info"]["success"]:
            # Handle failure to parse PR URL
            error_result = {
                "error": f"Failed to parse PR URL: {input_data['pr_info']['error']}",
                "pr_url": pr_url
            }
            self.logger.error(f"Failed to parse PR URL: {input_data['pr_info']['error']}")
            self.record_action(error_result, subdir="errors")
            return error_result
            
        if not input_data["branches"]["success"]:
            # Handle failure to get branch info
            error_result = {
                "error": f"Failed to get branch info: {input_data['branches']['error']}",
                "pr_url": pr_url
            }
            self.logger.error(f"Failed to get branch info: {input_data['branches']['error']}")
            self.record_action(error_result, subdir="errors")
            return error_result
            
        if not input_data["commits"]["success"]:
            # Handle failure to get commit info
            error_result = {
                "error": f"Failed to get commit info: {input_data['commits']['error']}",
                "pr_url": pr_url
            }
            self.logger.error(f"Failed to get commit info: {input_data['commits']['error']}")
            self.record_action(error_result, subdir="errors")
            return error_result
        
        # All checks passed, proceed with review
        self.logger.info(f"Starting review with {len(input_data['commits']['commits'])} commits")
        results = self.act(input_data)
        
        # Create a prefix based on the verdict and PR info
        prefix = ""
        if "final_verdict" in results and "pr_info" in results:
            pr_info = results["pr_info"]
            
            # Use the verdict_decision field if available, otherwise extract from text
            if "verdict_decision" in results:
                decision = results["verdict_decision"].lower()
            else:
                # Legacy fallback - extract verdict (approve, changes, or comment)
                verdict_text = results["final_verdict"]
                if "APPROVE" in verdict_text:
                    decision = "approve"
                elif "REQUEST_CHANGES" in verdict_text:
                    decision = "changes"
                else:
                    decision = "comment"
                
            prefix = f"{pr_info['owner']}_{pr_info['repo']}_{pr_info['number']}_{decision}_"
            self.logger.info(f"Review complete with verdict: {decision}")
        
        # Save the review results using the parent class's record_action method
        self.logger.info("Saving review results")
        review_file = self.record_action(results, subdir="reviews", prefix=prefix)
        
        # Add the file path to the results
        results["review_file"] = str(review_file)
        self.logger.info(f"Results saved to {review_file}")
        
        # If test mode is enabled, clean up the files
        if test_mode:
            self.logger.info("Test mode active - cleaning up created files")
            count = self.cleanup_files()
            self.logger.info(f"Cleaned up {count} files")
        
        return results

    def record_action(self, output: Dict[str, Any], subdir: str = None, prefix: str = None) -> Path:
        """
        Override record_action to track created files.
        
        Args:
            output: Data to save
            subdir: Subdirectory within agent_root to save to
            prefix: Optional prefix for the filename
            
        Returns:
            Path to the saved file
        """
        # Call parent class method to save the file
        output_path = super().record_action(output, subdir, prefix)
        
        # Track the created file
        self.created_files.append(output_path)
        
        return output_path
        
    def cleanup_files(self):
        """
        Clean up all files created by this agent instance.
        
        Returns:
            int: Number of files removed
        """
        count = 0
        for file_path in self.created_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    count += 1
            except Exception as e:
                self.logger.warning(f"Failed to remove file {file_path}: {str(e)}")
        
        self.logger.info(f"Cleaned up {count} files in test mode")
        self.created_files = []  # Reset the list
        
        return count

    def format_output_markdown(self, data: Dict[str, Any]) -> str:
        """
        Override the base format_output_markdown to format commit reviews in a structured way.
        
        Args:
            data: Dictionary of output data
            
        Returns:
            Formatted markdown string
        """
        lines = [f"# CogniAgent Output — {self.name}", ""]
        lines.append(f"**Generated**: {datetime.utcnow().isoformat()}")
        lines.append("")
        
        for k, v in data.items():
            if k == "commit_reviews":
                lines.append(f"## {k}")
                # Process each commit review as structured markdown
                for i, review in enumerate(v):
                    if i > 0:
                        lines.append("\n---\n")  # Add separator between reviews
                    
                    # Format commit header with sha and message
                    lines.append(f"### Commit {review['commit_sha']}: {review['commit_message']}")
                    
                    # Add the review content
                    lines.append(f"{review['review']}\n")
            elif isinstance(v, dict):
                lines.append(f"## {k}")
                for sub_k, sub_v in v.items():
                    lines.append(f"**{sub_k}**:\n{sub_v}\n")
            else:
                lines.append(f"## {k}")
                lines.append(f"{v}\n")
        
        lines.append("---")
        lines.append(f"> Agent: {self.name}")
        lines.append(f"> Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Join all lines and apply logseq-friendly replacements
        output = "\n".join(lines)
        
        # Replace "PR #X" with "#PR_X" for better logseq mapping
        output = re.sub(r"PR #(\d+)", r"#PR_\1", output)
        
        return output 