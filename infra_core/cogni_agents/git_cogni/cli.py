#!/usr/bin/env python
"""
CLI interface for GitCogniAgent
"""

import sys
import os
import json
from pathlib import Path

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent


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
      --verbose, -v     Show verbose logs
      --test, -t        Test mode - clean up created files after successful execution
    
    Examples:
      git-cogni https://github.com/derekg1729/CogniDAO/pull/2
      git-cogni https://github.com/derekg1729/CogniDAO/pull/2 --test
    """
    print(help_text)


def main():
    """Main CLI entry point for GitCogniAgent."""
    # Parse arguments
    verbose = False
    test_mode = False
    pr_url = None
    
    # Process arguments with simple parsing
    for arg in sys.argv[1:]:
        if arg.startswith('-h') or arg.startswith('--h'):
            print_help()
            sys.exit(0)
        elif arg == '--verbose' or arg == '-v':
            verbose = True
        elif arg == '--test' or arg == '-t':
            test_mode = True
        elif not arg.startswith('-'):
            pr_url = arg
    
    # Check if we have a PR URL
    if not pr_url:
        print_help()
        sys.exit(1)
    
    # Setup logging using agent's method (this returns a logger)
    logger = GitCogniAgent.setup_logging(verbose)
    
    logger.info(f"Starting PR review: {pr_url}")
    if test_mode:
        logger.info("Running in test mode - files will be cleaned up after successful execution")
    
    # Setup agent
    agent_root = Path(os.path.dirname(os.path.abspath(__file__)))
    agent = GitCogniAgent(agent_root=agent_root)
    
    # Run review
    try:
        # Use the agent's review_and_save method which does all the work
        result = agent.review_and_save(pr_url, test_mode=test_mode)
        
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
        
        # Get decision using agent's helper
        if "verdict_decision" in result:
            decision = result["verdict_decision"]
        else:
            # Fallback to helper method
            decision = agent.get_verdict_from_text(result.get("final_verdict", ""))
            
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