from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseCogniMemory(ABC):
    """Abstract base class for all memory backends used by Cogni agents."""

    @abstractmethod
    def read_history_dicts(self) -> List[Dict[str, Any]]:
        """Load serialized message history from memory."""
        pass

    @abstractmethod
    def write_history_dicts(self, history: List[Dict[str, Any]]) -> None:
        """Save serialized message history to memory."""
        pass

    @abstractmethod
    def write_context(self, file_name: str, content: Any, is_json: bool = False) -> None:
        """Write arbitrary context or document to memory."""
        pass

    # Optional but recommended for detailed logging/action recording
    @abstractmethod
    def log_decision(self, decision_data: Dict[str, Any]) -> None:
        """Log a decision point or specific action metadata."""
        pass

    @abstractmethod
    def clear_session(self) -> None:
        """Clear or reset session-specific memory (used for cleanup or test resets)."""
        pass

    # Optional utility methods that might be common
    # def _read_file(self, file_name: str) -> str | None:
    #     """Reads string content from a file (implementation specific)."""
    #     pass 