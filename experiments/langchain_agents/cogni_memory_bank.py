import json
import shutil # Added for directory removal
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

# Required imports for the two classes
from pydantic import Field, BaseModel # Use BaseModel for standard Pydantic class
from langchain_core.memory import BaseMemory
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict, HumanMessage, AIMessage


# --- Core Memory Bank Class (No LangChain Inheritance) ---
class CogniMemoryBank(BaseModel):
    """Core logic for managing memory files for a specific project and session.

    Handles file I/O operations within a structured directory:
    <memory_bank_root>/<project_name>/<session_id>/

    This class does NOT interact directly with LangChain message objects.
    It deals with Python dictionaries for history and arbitrary content for other files.
    """

    memory_bank_root: Path = Field(..., description="Root directory for all memory banks.")
    project_name: str = Field(..., description="Name of the project for memory isolation.")
    session_id: str = Field(default_factory=lambda: datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f'),
                            description="Unique identifier for the current session.")

    # --- Core Path Management ---

    def _get_session_path(self) -> Path:
        """Get the base directory path for the current project and session."""
        return self.memory_bank_root / self.project_name / self.session_id

    def _ensure_session_path_exists(self) -> Path:
        """Ensures the session directory exists and returns its path."""
        session_path = self._get_session_path()
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def _get_file_path(self, file_name: str) -> Path:
         """Get the full path for a file within the session directory."""
         return self._get_session_path() / file_name

    # --- Core File I/O Methods ---

    def _write_file(self, file_name: str, content: str):
        """Writes string content to a file, overwriting if it exists."""
        file_path = self._get_file_path(file_name)
        self._ensure_session_path_exists()
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            # Consider adding logging here
        except Exception as e:
            print(f"Error writing file {file_path}: {e}") # Replace with logger

    def _append_line(self, file_name: str, line: str):
        """Appends a line of text to a file."""
        file_path = self._get_file_path(file_name)
        self._ensure_session_path_exists()
        try:
            with open(file_path, 'a') as f:
                f.write(line + '\n')
            # Consider adding logging here
        except Exception as e:
            print(f"Error appending to file {file_path}: {e}") # Replace with logger

    def _read_file(self, file_name: str) -> str | None:
         """Reads string content from a file."""
         file_path = self._get_file_path(file_name)
         if not file_path.exists():
             return None
         try:
             with open(file_path, 'r') as f:
                 return f.read()
         except Exception as e:
            print(f"Error reading file {file_path}: {e}") # Replace with logger
            return None

    # --- History Management ---

    def read_history_dicts(self) -> List[Dict[str, Any]]:
        """Reads the conversation history from history.json.

        Returns:
            List of dictionaries representing the messages, or empty list if error/not found.
        """
        history_path = self._get_file_path("history.json")
        if history_path.exists():
            try:
                with open(history_path, 'r') as f:
                    history_dicts = json.load(f)
                # Basic validation could be added here if needed
                return history_dicts if isinstance(history_dicts, list) else []
            except (json.JSONDecodeError, TypeError, OSError) as e:
                print(f"Error loading or parsing history file {history_path}: {e}") # Replace with logger
                return []
        else:
            return []

    def write_history_dicts(self, history_dicts: List[Dict[str, Any]]) -> None:
        """Writes the conversation history to history.json.

        Args:
            history_dicts: A list of dictionaries representing the messages.
        """
        history_path = self._get_file_path("history.json")
        self._ensure_session_path_exists()
        try:
            with open(history_path, 'w') as f:
                json.dump(history_dicts, f, indent=2)
        except (TypeError, OSError) as e:
            print(f"Error saving history file {history_path}: {e}") # Replace with logger

    # --- General Context/Logging Methods ---

    def write_context(self, file_name: str, content: Any, is_json: bool = False):
        """Writes arbitrary context data to a file within the session directory."""
        session_path = self._ensure_session_path_exists()
        file_path = session_path / file_name

        try:
            with open(file_path, 'w') as f:
                if is_json:
                    json.dump(content, f, indent=2)
                else:
                    f.write(str(content))
            print(f"Context written to {file_path}") # Replace with logger
        except Exception as e:
            print(f"Error writing context file {file_path}: {e}") # Replace with logger

    def log_decision(self, decision_data: Dict[str, Any]):
        """Logs a decision point by appending to decisions.jsonl."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            **decision_data
        }
        try:
            json_line = json.dumps(log_entry)
            self._append_line("decisions.jsonl", json_line)
            print(f"Decision logged to {self._get_file_path('decisions.jsonl')}") # Replace with logger
        except (TypeError) as e:
             print(f"Error serializing decision data: {e}") # Replace with logger
        # Note: _append_line handles file IO errors

    def update_progress(self, progress_data: Dict[str, Any]):
        """Updates the overall progress/state by overwriting progress.json."""
        file_path = self._get_file_path("progress.json")
        self._ensure_session_path_exists()
        try:
             with open(file_path, 'w') as f:
                 json.dump(progress_data, f, indent=2)
             print(f"Progress updated in {file_path}") # Replace with logger
        except (TypeError, OSError) as e:
            print(f"Error updating progress file {file_path}: {e}") # Replace with logger


    # Renamed 'clear' to 'clear_session' and changed functionality
    def clear_session(self) -> None:
        """Clears the memory for the current session by deleting its directory."""
        session_path = self._get_session_path()
        if session_path.exists() and session_path.is_dir():
            try:
                shutil.rmtree(session_path)
                print(f"Cleared session directory: {session_path}") # Replace with logger
            except OSError as e:
                 print(f"Error clearing session directory {session_path}: {e}") # Replace with logger

    # --- Export Functionality ---

    def export_history_markdown(self) -> str:
        """Exports the conversation history as a Markdown formatted string."""
        history_dicts = self.read_history_dicts()
        markdown_lines = ["# Conversation History"]

        if not history_dicts:
            return "# Conversation History\n\n*No history found.*"

        for msg_dict in history_dicts:
            msg_type = msg_dict.get("type", "unknown").capitalize()
            msg_content = msg_dict.get("data", {}).get("content", "*No content*")

            markdown_lines.append(f"\n## {msg_type}")
            # Basic formatting - assumes content is plain text
            markdown_lines.append(msg_content)

        return "\n".join(markdown_lines)


# --- LangChain Adapter Class ---

class CogniLangchainMemoryAdapter(BaseMemory):
    """LangChain BaseMemory adapter for CogniMemoryBank.

    Wraps a CogniMemoryBank instance to provide the standard LangChain
    memory interface (load_memory_variables, save_context, clear).
    Handles the conversion between LangChain message objects and the
    dictionary format used by CogniMemoryBank.
    """

    memory_bank: CogniMemoryBank

    # Input/Output keys - adapt based on how Runnable/Chain expects them
    # These might need to become configurable.
    human_input_key: str = "input"
    ai_output_key: str = "output"

    @property
    def memory_variables(self) -> List[str]:
        """Defines that this memory returns 'history' key."""
        return ["history"]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, List[BaseMessage]]:
        """Load history from the memory bank and return as LangChain messages."""
        history_dicts = self.memory_bank.read_history_dicts()
        if history_dicts:
            try:
                messages = messages_from_dict(history_dicts)
                return {"history": messages}
            except Exception as e:
                print(f"Error converting dicts to messages: {e}") # Replace with logger
                return {"history": []}
        else:
            return {"history": []}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save the input and output messages to the memory bank."""
        try:
            input_str = inputs[self.human_input_key]
            output_str = outputs[self.ai_output_key]
        except KeyError as e:
            print(f"Error: Missing expected key '{e}' in inputs/outputs for saving context.") # Replace with logger
            return

        # Load existing history dicts
        # This load-modify-save isn't ideal for concurrency but simplest for now
        history_dicts = self.memory_bank.read_history_dicts()

        # Create new message dicts and append
        # This assumes Human->AI pairs; more complex flows might need different logic
        human_message_dict = messages_to_dict([HumanMessage(content=input_str)])[0]
        ai_message_dict = messages_to_dict([AIMessage(content=output_str)])[0]

        history_dicts.extend([human_message_dict, ai_message_dict])

        # Save updated history dicts
        self.memory_bank.write_history_dicts(history_dicts)

    def clear(self) -> None:
        """Clear the underlying session memory in the memory bank."""
        self.memory_bank.clear_session()

    print("Adapter clear successful.")