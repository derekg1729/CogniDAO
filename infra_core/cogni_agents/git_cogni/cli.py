#!/usr/bin/env python
"""
CLI interface for GitCogniAgent
"""

import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from infra_core.cogni_agents.git_cogni.git_cogni import GitCogniAgent
from infra_core.memory.memory_bank import CogniMemoryBank

# Import the constant for memory bank root
from infra_core.constants import MEMORY_BANKS_ROOT, AGENTS_DATA_ROOT


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
    
    # Setup logging using agent's method
    GitCogniAgent.setup_logging(verbose)
    
    # Setup agent
    # Define agent-specific root for external files (e.g., reviews/errors)
    # This should ideally also come from constants or config
    # agent_root = Path(os.path.dirname(os.path.abspath(__file__)))
    # Let's use the AGENTS_DATA_ROOT/git-cogni for consistency
    agent_root = AGENTS_DATA_ROOT / "git-cogni"
    agent_root.mkdir(parents=True, exist_ok=True) # Ensure it exists
    
    # Create a default memory bank instance for the agent
    # CLI runs are typically transient, so a default session is okay.
    cli_memory = CogniMemoryBank(
        memory_bank_root=MEMORY_BANKS_ROOT,
        project_name="core", # Or a CLI-specific project?
        session_id="main" # Default main session
    )
    
    agent = GitCogniAgent(
        agent_root=agent_root, # Root for external files
        memory=cli_memory # Pass the memory bank instance
    )
    
    # Run review
    try:
        # Use the agent's review_and_save method which does all the work
        result = agent.review_and_save(pr_url, test_mode=test_mode)
        
        # Check for errors
        if "error" in result:
            print(f"Error: {result['error']}")
            sys.exit(1)
        
        # Get decision using agent's helper
        if "verdict_decision" in result:
            decision = result["verdict_decision"]
        else:
            # Fallback to helper method
            decision = agent.get_verdict_from_text(result.get("final_verdict", ""))
            
        # Print final results
        print("-" * 80)
        print(f"PR Review completed: {decision}")
        
        # Show detailed review file location
        review_file = result.get('review_file', f"{agent_root}/reviews/")
        print(f"Review saved to: {review_file}")
        print("-" * 80)
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 