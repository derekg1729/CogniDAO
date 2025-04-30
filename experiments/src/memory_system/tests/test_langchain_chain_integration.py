"""
Integration test for LangChain chain with CogniStructuredMemoryAdapter.

This module contains functional tests that verify the integration between LangChain
and our custom memory components. The tests use mocked LLMs to focus on testing:
- LangChain's LLMChain execution pipeline
- Prompt templating with input + memory
- Custom CogniStructuredMemoryAdapter logic
- StructuredMemoryBank persistence
- Chroma-based semantic retrieval

For full integration tests with real LLMs, see test_langchain_integration_e2e.py
"""

import pytest
import tempfile
import shutil
import os
from doltpy.cli import Dolt
from langchain_core.language_models.fake import FakeListLLM

from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from experiments.src.memory_system.langchain_adapter import CogniStructuredMemoryAdapter
from experiments.src.memory_system.structured_memory_bank import StructuredMemoryBank
from experiments.src.memory_system.initialize_dolt import initialize_dolt_db

# Add import for schema registration
from experiments.src.memory_system.dolt_schema_manager import register_all_metadata_schemas


@pytest.fixture
def temp_dirs():
    """Create temporary directories for Dolt and ChromaDB, and initialize Dolt."""
    temp_dir = tempfile.mkdtemp()
    dolt_dir = os.path.join(temp_dir, "dolt")
    chroma_dir = os.path.join(temp_dir, "chroma")
    os.makedirs(dolt_dir)
    os.makedirs(chroma_dir)

    # Initialize Dolt repository (redundant if initialize_dolt_db does it, but safe)
    try:
        Dolt.init(dolt_dir)
    except Exception as e:
        # Handle potential errors if Dolt CLI isn't found or init fails
        pytest.fail(f"Failed to initialize Dolt repository in {dolt_dir}: {e}")

    # Initialize Dolt tables and schemas using the script
    if not initialize_dolt_db(dolt_dir):
        # If initialization fails, fail the test setup
        pytest.fail(f"Failed to initialize Dolt database using initialize_dolt_db in {dolt_dir}")

    yield dolt_dir, chroma_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_bank(temp_dirs):
    """Create a StructuredMemoryBank instance with temporary directories."""
    dolt_dir, chroma_dir = temp_dirs

    # Register schemas *after* initializing Dolt DB in temp_dirs
    registration_results = register_all_metadata_schemas(db_path=dolt_dir)
    if not all(registration_results.values()):
        pytest.fail(f"Failed to register one or more schemas: {registration_results}")

    return StructuredMemoryBank(
        dolt_db_path=dolt_dir, chroma_path=chroma_dir, chroma_collection="test_collection"
    )


@pytest.fixture
def cogni_memory(memory_bank):
    """Create a CogniStructuredMemoryAdapter instance."""
    return CogniStructuredMemoryAdapter(memory_bank=memory_bank)


@pytest.fixture
def fake_llm():
    """Create a FakeListLLM that returns predictable responses."""
    return FakeListLLM(responses=["This is a test response."])


def test_langchain_chain_with_memory_creates_block(cogni_memory, fake_llm):
    """
    Functional test verifying that LangChain chain execution creates a memory block.

    This test mocks the LLM but exercises:
    - LangChain's LLMChain execution pipeline
    - Prompt templating with input + memory
    - Custom CogniStructuredMemoryAdapter logic
    - StructuredMemoryBank persistence
    - Chroma-based semantic retrieval

    For full integration tests with real LLMs, see test_langchain_integration_e2e.py
    """
    # Create a simple prompt template
    prompt_template = """
    You are a helpful assistant. Here's what I know from memory:
    {relevant_blocks}
    
    Please respond to: {input}
    """

    prompt = PromptTemplate(input_variables=["input", "relevant_blocks"], template=prompt_template)

    # Create the chain with memory
    chain = LLMChain(llm=fake_llm, prompt=prompt, memory=cogni_memory)

    # Run the chain with some input
    input_text = "What is the capital of France?"
    inputs = {
        "input": input_text,
        "session_id": "test_session",
        "model": "fake-llm",
        "token_count": {"prompt": 10, "completion": 5},
        "latency": 0.1,
    }

    # Run the chain and get the output
    output = chain(inputs)

    # Verify the response
    assert output["text"] == "This is a test response.", f"Unexpected result: {output}"

    # Verify that a memory block was created
    memory_blocks = cogni_memory.memory_bank.query_semantic(query_text="capital of France", top_k=1)

    assert len(memory_blocks) == 1, "Expected exactly one memory block to be created"
    block = memory_blocks[0]

    # Verify block properties
    assert block.type == "log", f"Expected block type 'log', got '{block.type}'"
    assert "capital of France" in block.text, "Input text not found in memory block"
    assert "This is a test response" in block.text, "Output text not found in memory block"
    assert "type:log" in block.tags, "Missing 'type:log' tag"
    assert any(tag.startswith("date:") for tag in block.tags), "Missing date tag"
    assert "timestamp" in block.metadata, "Missing timestamp in metadata"
    assert "tool" in block.metadata, "Missing tool name in metadata"
    assert block.metadata["tool"] == "LogInteractionBlockTool", "Incorrect tool name in metadata"

    # Verify additional metadata
    assert block.metadata["model"] == "fake-llm", "Model name not saved in metadata"
    assert block.metadata["session_id"] == "test_session", "Session ID not saved in metadata"
    assert block.metadata["token_count"] == {"prompt": 10, "completion": 5}, (
        "Token count not saved in metadata"
    )
    assert block.metadata["latency_ms"] == 0.1, "Latency not saved in metadata"
