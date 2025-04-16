# MockMemoryBank for testing agent workflows without disk I/O
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# Import the base class
from .base import BaseCogniMemory

class MockMemoryBank(BaseModel, BaseCogniMemory):
    """
    In-memory mock of BaseCogniMemory for use in testing and LangGraph flows.
    Stores all data in dicts/lists. No file I/O. Logs all writes.
    Inherits from BaseCogniMemory to ensure interface compliance.
    """

    # Added session_id to match CogniMemoryBank interface used in tests/flow logs
    session_id: str = Field(default_factory=lambda: f"mock_session_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}")

    preset_history: List[Dict[str, Any]] = Field(default_factory=list, description="Pre-loaded history for tests.")
    preset_context: Dict[str, str] = Field(default_factory=dict, description="Pre-loaded context docs for tests.")

    # In-memory stores
    history_dicts: List[Dict[str, Any]] = Field(default_factory=list)
    context_written: Dict[str, str] = Field(default_factory=dict)
    logs: List[Dict[str, Any]] = Field(default_factory=list)

    # --- Implementation of BaseCogniMemory --- 

    def read_history_dicts(self) -> List[Dict[str, Any]]:
        """Returns dynamically written or preset history."""
        # Prioritize dynamically written history if it exists
        return self.history_dicts if self.history_dicts else self.preset_history

    def write_history_dicts(self, history: List[Dict[str, Any]]) -> None:
        """Overwrite history."""
        # Clear preset if dynamic is written
        self.preset_history = [] 
        self.history_dicts = history

    def write_context(self, file_name: str, content: Any, is_json: bool = False): # Matches base signature
        """Write context (tracked in memory)."""
        # Clear preset if dynamic is written
        if file_name in self.preset_context:
            del self.preset_context[file_name]
        self.context_written[file_name] = json.dumps(content, indent=2) if is_json else str(content)

    def log_decision(self, decision_data: Dict[str, Any]): # Matches base signature
        """Append log entry with timestamp."""
        self.logs.append({"timestamp": datetime.utcnow().isoformat(), **decision_data})

    def clear_session(self) -> None: # Matches base signature
        """Reset memory state."""
        self.history_dicts = []
        self.context_written = {}
        self.logs = []
        # Also clear presets? Or keep them for subsequent test runs?
        # Let's clear them for a full reset.
        self.preset_history = []
        self.preset_context = {}

    # --- Additional Helper/Mock-specific methods ---

    def _read_file(self, file_name: str) -> Optional[str]:
        """Internal helper: Return context if written or preloaded."""
        # Prioritize dynamically written context
        return self.context_written.get(file_name) or self.preset_context.get(file_name)

    def export_history_markdown(self) -> str:
        """Convert history to simple markdown for inspection."""
        current_history = self.read_history_dicts()
        if not current_history:
            return "# Conversation History\n\n*No history found.*"

        lines = ["# Conversation History"]
        for msg in current_history:
            role = msg.get("type", "Unknown").capitalize()
            content = msg.get("data", {}).get("content", "(No content)")
            lines.append(f"\n## {role}\n{content}")
        return "\n".join(lines)

    def update_progress(self, progress_data: Dict[str, Any]):
        """Simulates updating progress by writing to context."""
        # Use the standard write_context method for consistency
        self.write_context("progress.json", progress_data, is_json=True) 