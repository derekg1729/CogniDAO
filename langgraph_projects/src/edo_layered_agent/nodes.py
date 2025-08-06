"""
EDO Layered Agent Nodes - Event-Decision-Outcome workflow nodes.
"""

import sys
from functools import partial
from pathlib import Path
from typing import Dict, Any

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.shared_utils import get_logger  # noqa: E402
from src.shared_utils.edo_hooks import edo_event_loader_node, next_edo_log_creator_node  # noqa: E402

logger = get_logger(__name__)


def create_edo_event_loader():
    """Create EDO event loader node with agent_id bound."""
    return partial(edo_event_loader_node, agent_id="edo_layered_agent")


def create_next_edo_log_creator():
    """Create next EDO log creator node with agent_id bound.""" 
    return partial(next_edo_log_creator_node, agent_id="edo_layered_agent")


def create_passthrough_node():
    """Create a passthrough node that just returns state unchanged."""
    
    async def passthrough_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Passthrough node - returns state unchanged."""
        logger.info("🔄 Passthrough node - state passed through unchanged")
        return state
    
    return passthrough_node