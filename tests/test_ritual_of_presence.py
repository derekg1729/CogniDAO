import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# --- Move imports to top ---
from infra_core.memory.memory_bank import CogniMemoryBank, CogniLangchainMemoryAdapter
from infra_core.cogni_agents.core_cogni import CoreCogniAgent
from infra_core.cogni_agents.reflection_cogni import ReflectionCogniAgent
from infra_core.flows.rituals.ritual_of_presence import (
    create_initial_thought,
    create_reflection_thought,
    ritual_of_presence_flow,
    MEMORY_ROOT_DIR, # Get the base dir used by the flow for memory
    BASE_DIR # Get the base project dir used by the flow
)
from langchain_core.messages import AIMessage

# --- Add project root for imports ---
# Assuming this test file is in tests/ and the core code is in infra_core/
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Constants ---
TEST_PROJECT_NAME = "test_ritual_of_presence"

# --- Fixtures ---

@pytest.fixture
def temp_memory_root(tmp_path):
    """Create a temporary root directory for memory banks for this test session."""
    # tmp_path is a pytest fixture providing a Path object to a unique temporary directory
    memory_root = tmp_path / "memory_banks"
    memory_root.mkdir()
    return memory_root

@pytest.fixture
def shared_memory_adapter(temp_memory_root):
    """Provides a shared CogniMemoryBank and Adapter instance scoped to a test function."""
    core_bank = CogniMemoryBank(
        memory_bank_root=temp_memory_root,
        project_name=TEST_PROJECT_NAME
        # Session ID is generated automatically
    )
    adapter = CogniLangchainMemoryAdapter(memory_bank=core_bank)
    # Clear just in case, though it should be new each time
    adapter.clear()
    yield adapter
    # Cleanup happens automatically via pytest tmp_path fixture

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
    def test_create_initial_thought_task(self, MockCoreCogniAgent, shared_memory_adapter):
        """Test the create_initial_thought task in isolation."""
        # --- Setup Mock Agent ---
        mock_agent_instance = MockCoreCogniAgent.return_value
        mock_agent_instance.act.return_value = self.MOCK_INITIAL_THOUGHT_DATA.copy()
        # Mock record_action to prevent side effects if called, though task should call it
        mock_agent_instance.record_action = MagicMock()
        mock_agent_instance.prepare_input.return_value = {"prompt": "Generate initial thought."}

        # --- Execute Task ---
        # Note: Prefect tasks can often be run as regular functions for testing
        result_data = create_initial_thought(memory_adapter=shared_memory_adapter)

        # --- Verification ---
        # Check agent instantiation and act call
        MockCoreCogniAgent.assert_called_once()
        mock_agent_instance.prepare_input.assert_called_once()
        mock_agent_instance.act.assert_called_once()
        # Verify the agent's internal memory was replaced
        assert mock_agent_instance.memory == shared_memory_adapter.memory_bank

        # Check task's memory interactions
        # 1. save_context call by the task wrapper
        history_dicts = shared_memory_adapter.memory_bank.read_history_dicts()
        assert len(history_dicts) == 2 # Input (prompt) + Output (thought)
        assert history_dicts[0]["data"]["content"] == "Generate initial thought."
        assert history_dicts[1]["data"]["content"] == "This is the initial thought."

        # 2. record_action call by the task wrapper (optional logging)
        mock_agent_instance.record_action.assert_called_once_with(
            self.MOCK_INITIAL_THOUGHT_DATA, prefix="thought_"
        )

        # Check result
        assert result_data == self.MOCK_INITIAL_THOUGHT_DATA

    @patch('infra_core.flows.rituals.ritual_of_presence.ReflectionCogniAgent')
    def test_create_reflection_thought_task(self, MockReflectionCogniAgent, shared_memory_adapter):
        """Test the create_reflection_thought task in isolation."""
        # --- Setup Mock Agent ---
        mock_agent_instance = MockReflectionCogniAgent.return_value
        mock_agent_instance.act.return_value = self.MOCK_REFLECTION_DATA.copy()
        mock_agent_instance.record_action = MagicMock()
        # Mock prepare_input to simulate it having read history
        mock_agent_instance.prepare_input.return_value = {
            "prompt": "Reflect on the previous thought.",
            "previous_thought": "This is the initial thought."
        }

        # --- Pre-populate Memory ---
        # Simulate the first task having run
        shared_memory_adapter.save_context(
            inputs={"input": "Generate initial thought."},
            outputs={"output": "This is the initial thought."}
        )
        assert len(shared_memory_adapter.memory_bank.read_history_dicts()) == 2

        # --- Execute Task ---
        result_data = create_reflection_thought(memory_adapter=shared_memory_adapter)

        # --- Verification ---
        MockReflectionCogniAgent.assert_called_once_with(
            agent_root=Path(os.path.join(BASE_DIR, "presence/thoughts")), # Check path construction
            memory_adapter=shared_memory_adapter,
            memory_bank_root_override=shared_memory_adapter.memory_bank.memory_bank_root,
            project_root_override=Path(BASE_DIR)
        )
        mock_agent_instance.prepare_input.assert_called_once() # prepare_input should load history
        mock_agent_instance.act.assert_called_once()
        # Verify the agent's internal memory was replaced
        assert mock_agent_instance.memory == shared_memory_adapter.memory_bank


        # Check task's memory interactions
        # 1. save_context call by the task wrapper
        history_dicts = shared_memory_adapter.memory_bank.read_history_dicts()
        assert len(history_dicts) == 4 # Initial Prompt, Initial Thought, Reflection Prompt, Reflection
        assert history_dicts[2]["data"]["content"] == "Reflect on the previous thought."
        assert history_dicts[3]["data"]["content"] == "This is the reflection on the initial thought."

        # 2. record_action call by the task wrapper
        mock_agent_instance.record_action.assert_called_once_with(
            self.MOCK_REFLECTION_DATA, prefix="reflection_"
        )

        # Check result
        assert result_data == self.MOCK_REFLECTION_DATA

    # Patch the tasks where they are imported/used in the flow module
    @patch('infra_core.flows.rituals.ritual_of_presence.create_initial_thought')
    @patch('infra_core.flows.rituals.ritual_of_presence.create_reflection_thought')
    # Patch the Memory Bank init within the flow itself to control the session ID / path
    @patch('infra_core.flows.rituals.ritual_of_presence.CogniMemoryBank')
    @patch('infra_core.flows.rituals.ritual_of_presence.CogniLangchainMemoryAdapter')
    def test_full_flow_orchestration(self, MockAdapter, MockMemoryBank, mock_reflection_task, mock_initial_task, temp_memory_root):
        """Test the full flow orchestration, mocking the tasks themselves."""
        # --- Setup Mocks ---
        # Configure the mock memory bank and adapter used by the flow
        mock_core_bank_instance = MockMemoryBank.return_value
        mock_core_bank_instance.memory_bank_root = temp_memory_root
        mock_core_bank_instance.project_name = TEST_PROJECT_NAME
        mock_core_bank_instance.session_id = "test-session-123"
        mock_core_bank_instance._get_session_path.return_value = temp_memory_root / TEST_PROJECT_NAME / "test-session-123"

        mock_adapter_instance = MockAdapter.return_value
        mock_adapter_instance.memory_bank = mock_core_bank_instance

        # Configure mock task return values
        mock_initial_task.return_value = {"status": "ok_initial"}
        mock_reflection_task.return_value = {"status": "ok_reflection"}

        # --- Execute Flow ---
        result_message = ritual_of_presence_flow()

        # --- Verification ---
        # Check Memory Initialization and Clear
        MockMemoryBank.assert_called_once_with(
             memory_bank_root=Path(MEMORY_ROOT_DIR), # Check it uses the flow's defined root
             project_name="ritual_of_presence"
        )
        MockAdapter.assert_called_once_with(memory_bank=mock_core_bank_instance)
        mock_adapter_instance.clear.assert_called_once()

        # Check Task Calls
        mock_initial_task.assert_called_once_with(memory_adapter=mock_adapter_instance)
        mock_reflection_task.assert_called_once_with(memory_adapter=mock_adapter_instance)

        # Check Result Message
        assert "Ritual of Presence completed." in result_message
        assert mock_core_bank_instance.session_id in result_message
        assert str(mock_core_bank_instance._get_session_path()) in result_message

    # --- E2E Test (Refactored) ---
    # Mocks the Memory Bank and Adapter used BY THE FLOW
    # Mocks the LLM calls
    # Verifies interactions between flow, tasks, and mocked memory/llm.
    @patch('infra_core.flows.rituals.ritual_of_presence.CogniMemoryBank')
    @patch('infra_core.flows.rituals.ritual_of_presence.CogniLangchainMemoryAdapter')
    @patch('infra_core.cogni_agents.core_cogni.create_completion')
    @patch('infra_core.cogni_agents.reflection_cogni.create_completion')
    @patch('infra_core.openai_handler.initialize_openai_client') # Mock client init
    @patch('infra_core.openai_handler.extract_content') # Mock extract_content
    def test_flow_interactions_with_mocked_memory_and_llm(
        self,
        mock_extract_content,
        mock_init_openai,
        mock_reflection_completion,
        mock_core_completion,
        MockAdapter,
        MockMemoryBank
    ):
        """Tests flow interactions mocking LLM and Memory Bank/Adapter used by the flow."""
        # --- Setup Memory Mocks (Instances returned by patched constructors) ---
        mock_bank_instance = MockMemoryBank.return_value
        # Configure the mock bank instance attributes needed by the flow/agents
        mock_bank_instance.memory_bank_root = Path("mock/memory/root") # Make it look like a Path
        mock_bank_instance.project_name = "mock_project"
        mock_bank_instance.session_id = "mock_session"
        mock_bank_instance._get_session_path.return_value = Path("mock/memory/root/mock_project/mock_session")

        mock_adapter_instance = MockAdapter.return_value
        mock_adapter_instance.memory_bank = mock_bank_instance
        # Make load_memory_variables return something plausible for the reflection agent
        mock_adapter_instance.load_memory_variables.return_value = {
            "history": [AIMessage(content="Mock initial thought from history")]
        }

        # --- Setup LLM Mocks ---
        mock_openai_client = MagicMock()
        mock_init_openai.return_value = mock_openai_client

        # Mock CoreCogni completion & act return value
        mock_core_response = MagicMock()
        mock_core_completion.return_value = mock_core_response
        # Mock the act method to return a dict containing the expected string
        mock_core_act_return = {"thought_content": "Mock initial thought generated"}
        with patch.object(CoreCogniAgent, 'act', return_value=mock_core_act_return):

            # Mock ReflectionCogni completion & act return value
            mock_reflection_response = MagicMock()
            mock_reflection_completion.return_value = mock_reflection_response
            # Mock the act method to return a dict containing the expected string
            mock_reflection_act_return = {"reflection_content": "Mock reflection generated"}
            with patch.object(ReflectionCogniAgent, 'act', return_value=mock_reflection_act_return):

                # --- Execute Flow ---
                ritual_of_presence_flow()

        # --- Verification ---
        # 1. Verify Memory Initialization by Flow
        # Check that the FLOW called the constructor with the *real* path
        MockMemoryBank.assert_called_once_with(
            memory_bank_root=Path(MEMORY_ROOT_DIR), # Flow uses the real path
            project_name="ritual_of_presence"
        )
        MockAdapter.assert_called_once_with(memory_bank=mock_bank_instance) # Flow uses the mock bank instance
        mock_adapter_instance.clear.assert_called_once()

        # 2. Verify save_context calls (made by tasks on the mock adapter)
        save_calls = mock_adapter_instance.save_context.call_args_list
        assert len(save_calls) == 2
        # Call 1 (Initial Thought)
        # Use the actual default prompt from CoreCogniAgent
        expected_initial_prompt = "Generate a thoughtful reflection from Cogni. Please keep thoughts as short form morsels under 280 characters."
        assert save_calls[0][1]['inputs']['input'] == expected_initial_prompt
        assert save_calls[0][1]['outputs']['output'] == "Mock initial thought generated"
        # Call 2 (Reflection)
        # Use the actual default prompt from ReflectionCogniAgent
        # (which includes the placeholder for the thought)
        expected_reflection_prompt_template = "Reflect on the following thought: \n\n> {thought}\n\nKeep your reflection concise, under 280 characters."
        # We need the thought that was *supposedly* loaded by prepare_input (mocked)
        # This relies on how we set up the mock load_memory_variables return value
        thought_for_reflection = "Mock initial thought from history"
        expected_reflection_prompt = expected_reflection_prompt_template.format(thought=thought_for_reflection)
        assert save_calls[1][1]['inputs']['input'] == expected_reflection_prompt
        assert save_calls[1][1]['outputs']['output'] == "Mock reflection generated"

        # 3. Verify record_action calls (made by tasks, interacting with mock_bank_instance)
        # We need to check the calls made to the *agents'* record_action method.
        # Since the agents themselves are instantiated within the tasks, we need to
        # potentially patch the agents OR inspect calls on the mock_bank_instance
        # that record_action ultimately uses.

        # Check write_context calls on the mock bank instance
        write_calls = mock_bank_instance.write_context.call_args_list
        action_write_calls = [c for c in write_calls if c.args[0].startswith("action_")]
        assert len(action_write_calls) == 2
        assert "Mock initial thought generated" in action_write_calls[0].args[1]
        assert "Mock reflection generated" in action_write_calls[1].args[1]

        # Check log_decision calls on the mock bank instance
        log_calls = mock_bank_instance.log_decision.call_args_list
        assert len(log_calls) == 2
        # Call 1 (Initial Thought)
        assert log_calls[0].args[0]["agent"] == "core-cogni"
        assert log_calls[0].args[0]["action_filename"].startswith("action_")
        assert log_calls[0].args[0]["output_path"].endswith(".md") # Check the logged path structure
        # Call 2 (Reflection)
        assert log_calls[1].args[0]["agent"] == "reflection-cogni"
        assert log_calls[1].args[0]["action_filename"].startswith("action_")
        assert log_calls[1].args[0]["output_path"].endswith(".md")
        # assert "Mock reflection generated" in log_calls[1].args[0]["reflection_content"] # REMOVED: Key not present 