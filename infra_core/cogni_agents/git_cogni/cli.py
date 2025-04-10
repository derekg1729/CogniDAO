#!/usr/bin/env python
"""
CLI interface for GitCogniAgent
"""

import sys
import os
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
    
    Examples:
      git-cogni https://github.com/derekg1729/CogniDAO/pull/2
    """
    print(help_text)


def main():
    """Main CLI entry point for GitCogniAgent."""
    # Parse arguments
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    
    # Check for help flags - look for any argument starting with -h or --h
    if sys.argv[1].startswith('-h') or sys.argv[1].startswith('--h'):
        print_help()
        sys.exit(0)

    pr_url = sys.argv[1]
    print(f"Reviewing PR: {pr_url}")
    
    # Setup agent
    agent_root = Path(os.path.dirname(os.path.abspath(__file__)))
    agent = GitCogniAgent(agent_root=agent_root)
    
    # Run review
    try:
        result = agent.review_and_save(pr_url)
        
        # Check for errors
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        
        # Print success info
        if "verdict" in result:
            print(f"Review completed.")
            
            # Extract decision
            verdict = result["final_verdict"]
            if "APPROVE" in verdict:
                decision = "APPROVE"
            elif "REQUEST_CHANGES" in verdict:
                decision = "REQUEST CHANGES"
            else:
                decision = "COMMENT"
                
            print(f"Verdict: {decision}")
            print(f"Results saved in {agent_root}/reviews/ and {agent_root}/summaries/")
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 