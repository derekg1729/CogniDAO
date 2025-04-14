import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from prefect import flow
import shutil # Import shutil for cleanup

# --- Project Constants Import (Moved up) ---
from infra_core.constants import MEMORY_BANKS_ROOT

# --- Memory & Langchain Imports ---
from infra_core.memory.memory_bank import CogniMemoryBank, CogniLangchainMemoryAdapter # Real implementation
from infra_core.memory.mock_memory import MockMemoryBank # Mock implementation
from infra_core.flows.rituals.ritual_of_presence import (
    create_initial_thought,
    create_reflection_thought,
    ritual_of_presence_flow # Get the base project dir used by the flow
)
from langchain_core.messages import HumanMessage, AIMessage, messages_to_dict

# --- Add project root for imports ---
# Assuming this test file is in tests/ and the core code is in infra_core/
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Test Constants ---
TEST_PROJECT_NAME = "test_ritual_of_presence"

# --- Fixtures ---

@pytest.fixture
def temp_memory_root(tmp_path):
    """Provides a dummy path, not actually used by MockMemoryBank."""
    return tmp_path / "mock_memory_root"

@pytest.fixture
def mock_memory_adapter():
    """Provides a Langchain adapter wrapping a MockMemoryBank."""
    mock_bank = MockMemoryBank() # No path needed
    adapter = CogniLangchainMemoryAdapter(memory_bank=mock_bank)
    adapter.clear() # Ensure clean state
    yield adapter
    # No explicit cleanup needed for the in-memory mock

@pytest.fixture(scope="function")
def cleanup_ritual_session():
    """Ensures the test ritual-session directory is removed after test run."""
    session_path = MEMORY_BANKS_ROOT / "ritual_of_presence" / "ritual-session"
    # Optional: Clear before test if needed, though flow doesn't clear anymore
    # if session_path.exists():
    #    shutil.rmtree(session_path)
    yield # Run the test
    # Cleanup after test
    if session_path.exists():
        shutil.rmtree(session_path, ignore_errors=True)

# --- Test Class ---

class TestRitualOfPresenceFlow:

    # Mock data for agent outputs
    MOCK_INITIAL_THOUGHT_DATA = {
        "timestamp": "2024-01-01-10:00",
        "thought_content": "This is the initial thought.",
        "prompt_used": "Generate initial thought.",
        "temperature_used": 0.8
    }
    MOCK_REFLECTION_DATA = {
        "timestamp": "2024-01-01-10:05",
        "reflection_content": "This is the reflection on the initial thought.",
        "reflected_on_thought": "This is the initial thought.",
        "prompt_used": "Reflect on the previous thought.",
        "temperature_used": 0.7
    }

    @patch('infra_core.flows.rituals.ritual_of_presence.CoreCogniAgent')
    def test_create_initial_thought_task(self, MockCoreCogniAgent, mock_memory_adapter):
        """Test the create_initial_thought task using MockMemoryBank."""
        # --- Setup Mock Agent ---
        mock_agent_instance = MockCoreCogniAgent.return_value
        mock_agent_instance.act.return_value = self.MOCK_INITIAL_THOUGHT_DATA.copy()
        mock_agent_instance.record_action = MagicMock() # Mock record_action directly
        mock_agent_instance.prepare_input.return_value = {"prompt": "Generate initial thought."}

        # --- Execute Task ---
        result_data = create_initial_thought(memory_adapter=mock_memory_adapter)

        # --- Verification ---
        MockCoreCogniAgent.assert_called_once()
        # Verify the agent's internal memory was replaced with the MockMemoryBank
        assert mock_agent_instance.memory == mock_memory_adapter.memory_bank

        # Check MockMemoryBank state
        # 1. History Dictionaries
        history = mock_memory_adapter.memory_bank.history_dicts
        assert len(history) == 2
        assert history[0]["data"]["content"] == "Generate initial thought."
        assert history[1]["data"]["content"] == "This is the initial thought."

        # 2. Logged Decisions (via mocked record_action)
        # We mocked record_action on the agent, so we check that mock
        mock_agent_instance.record_action.assert_called_once_with(
            self.MOCK_INITIAL_THOUGHT_DATA, prefix="thought_"
        )

        assert result_data == self.MOCK_INITIAL_THOUGHT_DATA

    @patch('infra_core.flows.rituals.ritual_of_presence.ReflectionCogniAgent')
    def test_create_reflection_thought_task(self, MockReflectionCogniAgent, mock_memory_adapter):
        """Test the create_reflection_thought task using MockMemoryBank."""
        # --- Setup Mock Agent ---
        mock_agent_instance = MockReflectionCogniAgent.return_value
        mock_agent_instance.act.return_value = self.MOCK_REFLECTION_DATA.copy()
        mock_agent_instance.record_action = MagicMock()
        mock_agent_instance.prepare_input.return_value = {
            "prompt": "Reflect on the previous thought.",
            "previous_thought": "This is the initial thought."
        }

        # --- Pre-populate Memory ---
        # Directly manipulate the mock bank's state
        mock_memory_adapter.memory_bank.preset_history = messages_to_dict([
            HumanMessage(content="Generate initial thought."),
            AIMessage(content="This is the initial thought.")
        ])
        # Ensure clear clears the dynamic history
        mock_memory_adapter.memory_bank.history_dicts = []
        assert len(mock_memory_adapter.memory_bank.read_history_dicts()) == 2 # Should read preset

        # --- Execute Task ---
        result_data = create_reflection_thought(memory_adapter=mock_memory_adapter)

        # --- Verification ---
        MockReflectionCogniAgent.assert_called_once()
        assert mock_agent_instance.memory == mock_memory_adapter.memory_bank

        # Check MockMemoryBank state
        # 1. History (should overwrite preset)
        history = mock_memory_adapter.memory_bank.history_dicts
        assert len(history) == 4 # Initial (Preset) + Reflection Prompt + Reflection
        assert history[0]["data"]["content"] == "Generate initial thought."
        assert history[1]["data"]["content"] == "This is the initial thought."
        assert history[2]["data"]["content"] == "Reflect on the previous thought."
        assert history[3]["data"]["content"] == "This is the reflection on the initial thought."

        # 2. Logged Decisions (via mocked record_action)
        mock_agent_instance.record_action.assert_called_once_with(
            self.MOCK_REFLECTION_DATA, prefix="reflection_"
        )

        assert result_data == self.MOCK_REFLECTION_DATA

    # Mock agent functions directly within the test file or import mocks
    @flow
    def mock_create_initial_thought(memory_adapter: CogniLangchainMemoryAdapter):
        print("Mock initial thought running")
        # Simulate interaction with memory_adapter if necessary
        memory_adapter.save_context({"input": "Initial trigger"}, {"output": "Mock initial thought generated"})
        return {"output": "Mock initial thought generated"}

    @flow
    def mock_create_reflection_thought(memory_adapter: CogniLangchainMemoryAdapter):
        print("Mock reflection thought running")
        # Simulate interaction with memory_adapter if necessary
        history = memory_adapter.load_memory_variables({})
        memory_adapter.save_context({"input": f"Reflecting on: {history}"}, {"output": "Mock reflection thought generated"})
        return {"output": "Mock reflection thought generated"}

    @patch('infra_core.flows.rituals.ritual_of_presence.create_reflection_thought', new=mock_create_reflection_thought)
    @patch('infra_core.flows.rituals.ritual_of_presence.create_initial_thought', new=mock_create_initial_thought)
    @patch('infra_core.flows.rituals.ritual_of_presence.CogniMemoryBank')
    def test_flow_with_mock_memory_and_mock_agents(self, mock_cogni_memory_bank_class):
        """
        Test the end-to-end flow with mocked CogniMemoryBank and mocked agent tasks.
        Verifies that the flow completes and returns the expected message format,
        including the correct session ID and path from the mocked memory bank.
        """
        # Configure the mock instance that the CogniMemoryBank class will return
        mock_instance = MagicMock(spec=CogniMemoryBank)
        mock_instance.session_id = 'flow-mock-session-123' # Directly set the attribute
        mock_session_path = Path('/mock/memory/ritual_of_presence/flow-mock-session-123')
        mock_instance._get_session_path.return_value = mock_session_path
        mock_cogni_memory_bank_class.return_value = mock_instance

        # --- Mock the adapter separately if needed, or rely on the bank mock ---
        # We also need CogniLangchainMemoryAdapter to use our mock_instance
        # Patching the adapter's constructor or its usage might be complex.
        # Let's assume for now the flow correctly instantiates it with the mocked bank.
        # If adapter methods are called directly in the test, mock them here.
        # For this flow, the adapter is created inside, so bank mock should suffice.

        # Run the flow
        result_message = ritual_of_presence_flow()

        # --- Assertions ---
        # 1. Check if CogniMemoryBank was instantiated (implicitly checked by return_value usage)
        mock_cogni_memory_bank_class.assert_called_once()
        # Example check on arguments if needed:
        # mock_cogni_memory_bank_class.assert_called_with(memory_bank_root=Path('data/memory'), project_name='ritual_of_presence')

        # 2. Check if the mock bank's methods were called as expected by the adapter/flow
        # The adapter calls the bank's clear_session method.
        # mock_instance.clear_session.assert_called_once() # REMOVED - clear is no longer called by the flow

        # 3. Check the final result message
        expected_session_id = 'flow-mock-session-123'
        expected_path_str = str(mock_session_path)

        print(f"Result Message: {result_message}") # Debug print
        print(f"Expected Session ID: {expected_session_id}")
        print(f"Expected Path String: {expected_path_str}")

        assert expected_session_id in result_message
        assert expected_path_str in result_message
        assert "Ritual of Presence completed." in result_message

        # 4. Verify agent mocks were called (implicitly done by patching them)
        # If specific calls/interactions within agents need checking, add assertions here
        # or mock the adapter passed to them and check calls on that adapter.

    # --- New Integration Test --- 
    @patch('infra_core.cogni_agents.reflection_cogni.ReflectionCogniAgent.act')
    @patch('infra_core.cogni_agents.core_cogni.CoreCogniAgent.act')
    def test_flow_creates_memory_files_in_correct_location(
        self,
        mock_core_act, 
        mock_reflection_act,
        cleanup_ritual_session # Use the cleanup fixture
    ):
        """
        Tests that the flow run creates expected files in the correct memory bank session.
        Mocks only the agent 'act' methods.
        """
        # --- Configure Mocks ---
        mock_core_act.return_value = {"thought_content": "Mock initial thought"}
        mock_reflection_act.return_value = {"reflection_content": "Mock reflection"}

        # --- Execute Flow ---
        result_message = ritual_of_presence_flow()
        print(f"Flow result: {result_message}") # For debugging

        # --- Verification ---
        expected_session_path = MEMORY_BANKS_ROOT / "ritual_of_presence" / "ritual-session"
        assert expected_session_path.is_dir(), f"Session directory not found: {expected_session_path}"

        core_thought_files = list(expected_session_path.glob("CoreCogniAgent_thought_*.md"))
        assert len(core_thought_files) >= 1, f"No CoreCogniAgent thought file found in {expected_session_path}"
        print(f"Found core thought file: {core_thought_files[0]}")

        reflection_files = list(expected_session_path.glob("ReflectionCogniAgent_reflection_*.md"))
        assert len(reflection_files) >= 1, f"No ReflectionCogniAgent reflection file found in {expected_session_path}"
        print(f"Found reflection file: {reflection_files[0]}")

        assert (expected_session_path / "history.json").is_file(), "history.json not found"
        assert (expected_session_path / "decisions.jsonl").is_file(), "decisions.jsonl not found"

# Test class ends implicitly here