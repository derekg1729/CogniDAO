#!/usr/bin/env python
"""
Example: Using OllamaModelHandler with GitCogniAgent

This script demonstrates how to use the OllamaModelHandler with GitCogniAgent
to review a PR using a local model from Ollama instead of OpenAI API.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

# Import after sys.path adjustment
from experiments.src.core.models.ollama_model_handler import OllamaModelHandler  # noqa: E402
from legacy_logseq.cogni_agents.git_cogni.git_cogni import GitCogniAgent  # noqa: E402
from legacy_logseq.memory.memory_bank import CogniMemoryBank  # noqa: E402
from legacy_logseq.constants import MEMORY_BANKS_ROOT  # noqa: E402


def main():
    """
    Main function to demonstrate using GitCogniAgent with OllamaModelHandler
    """
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("gitcogni_ollama_example")
    logger.info("Starting GitCogni with Ollama example")

    # Set up paths
    memory_bank_root = Path(MEMORY_BANKS_ROOT)
    agent_root = project_root / "data/gitcogni_ollama_example"

    # Create memory bank for agent
    session_id = f"ollama_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    memory_bank = CogniMemoryBank(
        memory_bank_root=memory_bank_root, project_name="experiments", session_id=session_id
    )

    # Create Ollama model handler
    logger.info("Creating OllamaModelHandler")
    model = OllamaModelHandler(
        default_model="deepseek-coder",  # Change this to match your available Ollama model
        api_url="http://localhost:11434/api",
        timeout=180,  # Longer timeout for potentially large requests
    )

    # Initialize GitCogniAgent with Ollama model handler
    logger.info("Initializing GitCogniAgent with Ollama model handler")
    agent = GitCogniAgent(
        agent_root=agent_root,
        memory=memory_bank,
        model=model,  # Pass our Ollama model handler
        external_logger=logger,
    )

    # For testing, review a small example PR
    # This could be any public GitHub PR
    pr_url = "https://github.com/derekg1729/CogniDAO/pull/4"

    try:
        logger.info(f"Starting PR review for: {pr_url}")
        results = agent.review_and_save(pr_url, test_mode=False)

        # Print results summary
        logger.info(f"Review completed: {results.get('verdict_decision', 'Unknown verdict')}")
        logger.info(f"Results saved to: {results.get('review_file', 'Unknown location')}")

    except Exception as e:
        logger.error(f"Error in GitCogni review: {e}", exc_info=True)
        # Make sure Ollama is running with the correct model
        print("\nDid you start Ollama with 'ollama serve'?")
        print("Did you pull the deepseek-coder model with 'ollama pull deepseek-coder'?")

    logger.info("Example completed")


if __name__ == "__main__":
    main()
