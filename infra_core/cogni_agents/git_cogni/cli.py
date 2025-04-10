#!/usr/bin/env python
"""
CLI interface for GitCogniAgent
"""

import sys
import os
import json
import logging
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent

# Configure logging
def setup_logging(verbose=False):
    """Setup logging for CLI usage with structured formatting."""
    level = logging.INFO  # Always use INFO level
    
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
    
    # Suppress excessive logging from libraries (more aggressive)
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
    # This is the key fix for double logging - we don't create a separate logger
    agent_logger = logging.getLogger('infra_core.cogni_agents.git_cogni.git_cogni')
    agent_logger.handlers = []  # Clear any existing handlers
    agent_logger.propagate = True  # Ensure it uses the root logger's handlers
    
    # Return the CLI logger for local use
    return logging.getLogger('gitcogni.cli')


def print_help():
    """Print help message."""
    help_text = """
    GitCogni PR Review Tool
    
    Usage: git-cogni <github-pr-url>
    
    Arguments:
      <github-pr-url>    URL of the GitHub pull request to review
                        (e.g., https://github.com/owner/repo/pull/123)
    
    Options:
      --help, -h        Show this help message and exit
    
    Examples:
      git-cogni https://github.com/derekg1729/CogniDAO/pull/2
    """
    print(help_text)


def main():
    """Main CLI entry point for GitCogniAgent."""
    # Parse arguments
    verbose = False
    pr_url = None
    
    # Process arguments with simple parsing
    for arg in sys.argv[1:]:
        if arg.startswith('-h') or arg.startswith('--h'):
            print_help()
            sys.exit(0)
        elif arg == '--verbose' or arg == '-v':
            verbose = True
        elif not arg.startswith('-'):
            pr_url = arg
    
    # Setup logging
    logger = setup_logging(verbose)
    
    # Check if we have a PR URL
    if not pr_url:
        print_help()
        sys.exit(1)
    
    logger.info(f"Starting PR review: {pr_url}")
    
    # Setup agent
    agent_root = Path(os.path.dirname(os.path.abspath(__file__)))
    agent = GitCogniAgent(agent_root=agent_root)
    
    # Manual instrumentation - add key logging points for monitoring
    def monitor_token_usage(operation, data):
        """Log information about operations with potential token usage"""
        if isinstance(data, str):
            char_length = len(data)
            word_count = len(data.split())
            logger.info(f"TOKEN MONITOR | {operation} | ~{word_count} words, {char_length} chars")
    
    # Patch the GitCogniAgent's review_pr method to add monitoring
    original_review_pr = agent.review_pr
    
    # Only patch if not already instrumented (check for a marker attribute)
    if not hasattr(agent, '_review_pr_instrumented'):
        def monitored_review_pr(*args, **kwargs):
            logger.info("Starting review process with instrumentation")
            
            # Monitor inputs
            if len(args) >= 3:
                git_cogni_context = args[0]
                pr_data = args[2]
                
                # Log context size
                monitor_token_usage("git_cogni_context", git_cogni_context)
                
                # Log PR data stats
                if pr_data and "commit_info" in pr_data and "commits" in pr_data["commit_info"]:
                    commits = pr_data["commit_info"]["commits"]
                    commit_stats = {
                        "commit_count": len(commits),
                        "total_files": sum(c.get("files_count", 0) for c in commits),
                        "total_diff_length": sum(c.get("diff_length", 0) for c in commits)
                    }
                    logger.info(f"REVIEW INPUT STATS: {json.dumps(commit_stats, indent=2)}")
            
            # Run original method
            result = original_review_pr(*args, **kwargs)
            
            # Monitor result size
            if "final_verdict" in result:
                monitor_token_usage("final_verdict", result["final_verdict"])
                
            return result
        
        # Apply the patch
        agent.review_pr = monitored_review_pr
        
        # Mark as instrumented to avoid double patching
        agent._review_pr_instrumented = True
    
    # Run review
    try:
        result = agent.review_and_save(pr_url)
        
        # Check for errors
        if "error" in result:
            logger.error(f"Review failed: {result['error']}")
            print(f"Error: {result['error']}")
            sys.exit(1)
        
        # Log commit stats
        if "commit_reviews" in result:
            commit_stats = {
                "commit_count": len(result["commit_reviews"]),
                "commit_shas": [c["commit_sha"] for c in result["commit_reviews"]]
            }
            logger.info(f"COMMIT STATS: {json.dumps(commit_stats, indent=2)}")
        
        # Extract decision
        verdict = result.get("final_verdict", "")
        if "APPROVE" in verdict:
            decision = "APPROVE"
        elif "REQUEST_CHANGES" in verdict:
            decision = "REQUEST CHANGES"
        else:
            decision = "COMMENT"
            
        # Print final results (not logged)
        logger.info(f"VERDICT: {decision}")
        print("-" * 80)
        print(f"PR Review completed: {decision}")
        
        # Show detailed review file location
        review_file = result.get('review_file', f"{agent_root}/reviews/")
        print(f"Review saved to: {review_file}")
        print("-" * 80)
        
    except Exception as e:
        logger.exception(f"Unexpected error during review process")
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 