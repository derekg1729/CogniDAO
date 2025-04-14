import json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

from pydantic import Field
from langchain_core.memory import BaseMemory
from langchain_core.messages import messages_from_dict, messages_to_dict

class CogniMemoryBank(BaseMemory):
    """A LangChain BaseMemory implementation inspired by memory-bank-mcp.

    This class manages memory for a specific project and session,
    storing conversation history and potentially other context
    in a structured directory layout using JSON files.
    """

    memory_bank_root: Path = Field(..., description="Root directory for all memory banks.")
    project_name: str = Field(..., description="Name of the project for memory isolation.")
    session_id: str = Field(default_factory=lambda: datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f'), 
                            description="Unique identifier for the current session.")
    
    # --- BaseMemory Implementation --- 

    @property
    def memory_variables(self) -> List[str]:
        """Defines the variables this memory class will return.
        
        For compatibility with LangChain Runnables/Chains, this typically includes 'history'
        or other keys expected by prompts.
        """
        # For now, align with the common pattern expected by MessagesPlaceholder
        return ["history"]

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load the conversation history for the current session.
        
        Args:
            inputs: Ignored in this implementation, history is loaded based on session.
            
        Returns:
            Dictionary with the key 'history' containing a list of BaseMessages.
        """
        history_path = self._get_history_file_path()
        if history_path.exists():
            try:
                with open(history_path, 'r') as f:
                    history_dicts = json.load(f)
                messages = messages_from_dict(history_dicts)
                return {"history": messages}
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading or parsing memory file {history_path}: {e}") # Replace with logger
                return {"history": []}
        else:
            return {"history": []}

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """Save the input and output messages to the session's history file.
        
        Args:
            inputs: Dictionary of input variables to the chain/runnable.
                    Expected to contain the user input message under a known key (e.g., 'input').
            outputs: Dictionary of output variables from the chain/runnable.
                     Expected to contain the AI response under a known key (e.g., 'output').
        """
        # Determine input/output keys (this might need refinement based on actual usage)
        # For now, assume single key/value pairs as in the previous flow
        try:
            input_key = list(inputs.keys())[0]
            input_str = inputs[input_key]
            output_key = list(outputs.keys())[0]
            output_str = outputs[output_key]
        except IndexError:
            print("Error: Could not determine input/output keys for saving context.") # Replace with logger
            return
            
        # Load existing history
        # Note: Avoid loading if just appending to avoid race conditions if possible,
        # but for now, load-read-append is simpler.
        loaded_vars = self.load_memory_variables({})
        current_history = loaded_vars.get("history", [])
        
        # Create message objects (assuming Human/AI pair for now)
        # This might need to be more flexible
        from langchain_core.messages import HumanMessage, AIMessage # Local import for clarity
        current_history.append(HumanMessage(content=input_str))
        current_history.append(AIMessage(content=output_str))

        # Save updated history
        history_path = self._get_history_file_path()
        history_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        try:
            history_dicts = messages_to_dict(current_history)
            with open(history_path, 'w') as f:
                json.dump(history_dicts, f, indent=2)
        except Exception as e:
            print(f"Error saving memory file {history_path}: {e}") # Replace with logger

    def clear(self) -> None:
        """Clear the memory for the current session by deleting its history file."""
        history_path = self._get_history_file_path()
        if history_path.exists():
            try:
                history_path.unlink()
            except OSError as e:
                 print(f"Error clearing memory file {history_path}: {e}") # Replace with logger
        # Consider clearing other session-specific files if added later

    # --- CogniMemoryBank Specific Methods (Inspired by memory-bank-mcp) --- 

    def _get_session_path(self) -> Path:
        """Get the base directory path for the current project and session."""
        return self.memory_bank_root / self.project_name / self.session_id

    def _get_history_file_path(self) -> Path:
        """Get the path to the primary conversation history file."""
        # Using a simple history.json for now
        return self._get_session_path() / "history.json"

    def write_context(self, file_name: str, content: Any, is_json: bool = False):
        """Writes arbitrary context data to a file within the session directory.
        
        Placeholder for saving things like intermediate thoughts, tool outputs etc.
        Inspired by memory-bank-mcp file writing.
        """
        session_path = self._get_session_path()
        session_path.mkdir(parents=True, exist_ok=True)
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
        # raise NotImplementedError("write_context needs implementation based on analysis.")

    def log_decision(self, decision_data: Dict[str, Any]):
        """Logs a decision point or significant event during the session.
        
        Placeholder inspired by memory-bank-mcp patterns.
        """
        # Potential implementation: Append to a decisions.jsonl file
        file_path = self._get_session_path() / "decisions.jsonl"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(file_path, 'a') as f:
                log_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    **decision_data
                }
                json.dump(log_entry, f)
                f.write('\n')
            print(f"Decision logged to {file_path}") # Replace with logger
        except Exception as e:
             print(f"Error logging decision to {file_path}: {e}") # Replace with logger
        # raise NotImplementedError("log_decision needs implementation based on analysis.")

    def update_progress(self, progress_data: Dict[str, Any]):
        """Updates a file tracking the overall progress or state of the session.
        
        Placeholder inspired by memory-bank-mcp patterns.
        """
        # Potential implementation: Overwrite a progress.json file
        file_path = self._get_session_path() / "progress.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        try:
             with open(file_path, 'w') as f:
                 json.dump(progress_data, f, indent=2)
             print(f"Progress updated in {file_path}") # Replace with logger
        except Exception as e:
            print(f"Error updating progress file {file_path}: {e}") # Replace with logger
        # raise NotImplementedError("update_progress needs implementation based on analysis.")

# Example Usage (for testing):
if __name__ == "__main__":
    # Configure root and project
    bank_root = Path("./_memory_banks") # Example root
    project = "test_project"

    # --- Test Initialization and Path --- 
    memory = CogniMemoryBank(memory_bank_root=bank_root, project_name=project)
    print(f"Session ID: {memory.session_id}")
    print(f"Session Path: {memory._get_session_path()}")
    print(f"History Path: {memory._get_history_file_path()}")
    memory.clear() # Start clean

    # --- Test Save/Load --- 
    print("\n--- Testing Save/Load ---")
    initial_load = memory.load_memory_variables({}) 
    print(f"Initial history: {initial_load}")

    inputs1 = {"input": "Hello AI!"}
    outputs1 = {"output": "Hello Human!"}
    memory.save_context(inputs1, outputs1)
    print("Saved first interaction.")

    loaded_after_1 = memory.load_memory_variables({}) 
    print(f"History after 1 save: {loaded_after_1}")

    inputs2 = {"input": "How are you?"}
    outputs2 = {"output": "I am functioning nominally."}
    memory.save_context(inputs2, outputs2)
    print("Saved second interaction.")
    
    loaded_after_2 = memory.load_memory_variables({}) 
    print(f"History after 2 saves: {loaded_after_2}")

    # --- Test Other Methods (Placeholders) ---
    print("\n--- Testing Other Methods ---")
    memory.write_context("thought.txt", "This is an intermediate thought.")
    memory.write_context("tool_output.json", {"tool": "calculator", "result": 42}, is_json=True)
    memory.log_decision({"action": "used_calculator", "parameters": {"input": "6*7"}})
    memory.update_progress({"status": "processing", "step": 3})

    # --- Test Clear --- 
    # print("\n--- Testing Clear ---")
    # memory.clear()
    # loaded_after_clear = memory.load_memory_variables({}) 
    # print(f"History after clear: {loaded_after_clear}")
    # print(f"History file exists after clear: {memory._get_history_file_path().exists()}")
    
    print(f"\nCheck the contents of {memory._get_session_path()}") 