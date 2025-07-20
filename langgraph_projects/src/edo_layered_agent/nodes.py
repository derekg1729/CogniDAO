"""
EDO Layered Agent Nodes - Event-Decision-Outcome workflow nodes.
"""

import sys
from pathlib import Path
from typing import Dict, Any

# Add src to path for absolute imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from src.shared_utils import get_logger  # noqa: E402
from src.shared_utils.edo_hooks import edo_event_loader_node, edo_decision_writer_node  # noqa: E402

logger = get_logger(__name__)


def create_edo_event_loader():
    """Create EDO event loader node."""
    return edo_event_loader_node


def create_edo_decision_writer():
    """Create EDO decision writer node.""" 
    return edo_decision_writer_node


def create_passthrough_node():
    """Create a passthrough node that just returns state unchanged."""
    
    async def passthrough_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """Passthrough node - returns state unchanged."""
        logger.info("🔄 Passthrough node - state passed through unchanged")
        return state
    
    return passthrough_node