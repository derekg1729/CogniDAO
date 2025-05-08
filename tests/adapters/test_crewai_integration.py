"""
Integration tests for CrewAI adapter with memory tools.

These tests verify that:
1. CrewAI agents can save and query memory blocks
2. Dolt commits are created correctly
3. LlamaIndex nodes are created and queried correctly
4. Error handling works as expected
"""

import json
import tempfile
import shutil
import pytest

# Ensure CogniTool has LangChain adapter patched before tools are imported
import infra_core.memory_system.tools.adapters.langchain_tool_adapter  # noqa: F401

from crewai import Agent, Crew, Task
from doltpy.cli import Dolt
from cogni_adapters.crewai import CogniMemoryStorage
from cogni_adapters.crewai.tools import create_memory_block_tool, query_memory_blocks_tool
from infra_core.memory_system.structured_memory_bank import StructuredMemoryBank
from infra_core.memory_system.schemas.memory_block import MemoryBlock
from infra_core.memory_system.initialize_dolt import initialize_dolt_db
from infra_core.memory_system.dolt_schema_manager import register_all_metadata_schemas


@pytest.fixture
def temp_dolt_dir():
    """Create a temporary directory for Dolt repository."""
    temp_dir = tempfile.mkdtemp()
    # Initialize a new Dolt repository
    _ = Dolt.init(temp_dir)
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir)


@pytest.fixture
def memory_bank(temp_dolt_dir):
    """Create a test memory bank with temporary Dolt repo."""
    # Ensure core tables exist
    init_success = initialize_dolt_db(temp_dolt_dir)
    assert init_success, "Failed to initialize Dolt tables for integration test"

    # Register metadata schemas so CreateMemoryBlock can resolve versions
    registration = register_all_metadata_schemas(db_path=temp_dolt_dir)
    assert all(registration.values()), f"Schema registration failed: {registration}"

    return StructuredMemoryBank(
        dolt_db_path=temp_dolt_dir,
        chroma_path=":memory:",  # Use in-memory Chroma DB for testing
        chroma_collection="test_collection",
    )


@pytest.fixture
def memory_storage(memory_bank):
    """Create a CogniMemoryStorage instance with test memory bank."""
    return CogniMemoryStorage(memory_bank)


@pytest.fixture
def thinker_agent(memory_storage, memory_bank):
    """Create a Thinker agent that can save memories."""
    return Agent(
        role="Thinker",
        goal="Save important thoughts and ideas",
        backstory="You are a thoughtful agent that saves important information.",
        tools=[create_memory_block_tool.as_langchain_tool(memory_bank=memory_bank)],
        external_memory=memory_storage,
        verbose=True,
        allow_delegation=False,  # Prevent task delegation
    )


@pytest.fixture
def reflector_agent(memory_storage, memory_bank):
    """Create a Reflector agent that can query memories."""
    return Agent(
        role="Reflector",
        goal="Retrieve and reflect on saved thoughts",
        backstory="You are a reflective agent that analyzes saved information.",
        tools=[query_memory_blocks_tool.as_langchain_tool(memory_bank=memory_bank)],
        external_memory=memory_storage,
        verbose=True,
        allow_delegation=False,  # Prevent task delegation
    )


def test_crewai_save_and_query(memory_bank, thinker_agent, reflector_agent):
    """Test that CrewAI agents can save and query memory blocks."""
    # Create a crew with both agents
    crew = Crew(
        agents=[thinker_agent, reflector_agent],
        tasks=[
            Task(
                description="""
                Save a thought about AI using the create_memory_block tool.
                
                Instructions:
                1. Use the create_memory_block tool to save the following information:
                   - text: "AI is an important field that is rapidly evolving and has great potential for transforming various industries."
                   - type: "knowledge"
                   - tags: ["AI", "technology", "future"]
                2. Return the tool's response as a JSON string.
                """,
                agent=thinker_agent,
                expected_output="""{
                    "text": "AI is an important field that is rapidly evolving and has great potential for transforming various industries.",
                    "type": "knowledge",
                    "tags": ["AI", "technology", "future"]
                }""",
            ),
            Task(
                description="""
                Query and analyze the previously saved thought using the query_memory_blocks tool.
                
                Instructions:
                1. Use the query_memory_blocks tool with:
                   - query: "AI technology and its impact"
                   - filters: {"type": "knowledge", "tags": ["AI"]}
                2. Return the tool's response as a JSON string.
                """,
                agent=reflector_agent,
                expected_output="""{
                    "query": "AI technology and its impact",
                    "filters": {
                        "type": "knowledge",
                        "tags": ["AI"]
                    }
                }""",
            ),
        ],
        verbose=True,
    )

    # Run the crew
    _ = crew.kickoff()

    # Verify memory operations
    # 1. Check that a memory block was created by CrewAI
    blocks = memory_bank.query_semantic("AI", top_k=1)
    assert len(blocks) > 0, "No memory blocks were created"
    block = blocks[0]
    assert isinstance(block, MemoryBlock), "Retrieved item is not a MemoryBlock"

    # Verify block content
    assert "ai" in block.text.lower(), "Block text does not contain 'AI'"
    assert block.type == "knowledge", "Block type is not 'knowledge'"
    assert "AI" in block.tags, "Block tags do not contain 'AI'"
    assert "technology" in block.tags, "Block tags do not contain 'technology'"
    assert "future" in block.tags, "Block tags do not contain 'future'"

    # 2. Verify Dolt commit exists
    repo = Dolt(memory_bank.dolt_db_path)
    commits = repo.log()
    assert len(commits) > 1, "No Dolt commits were created"

    # 3. Verify LlamaIndex node exists using the retriever
    assert memory_bank.llama_memory.is_ready(), "LlamaIndex is not ready"
    retriever = memory_bank.llama_memory.index.as_retriever(similarity_top_k=1)
    retrieved_nodes = retriever.retrieve(block.id)
    assert len(retrieved_nodes) > 0, "Node was not found in LlamaIndex via retriever"
    assert retrieved_nodes[0].node.node_id == block.id, (
        "Retrieved node ID does not match created block ID"
    )


def test_crewai_error_handling(memory_bank, thinker_agent):
    """Test error handling in CrewAI memory operations."""
    # Create a crew with just the thinker agent
    crew = Crew(
        agents=[thinker_agent],
        tasks=[
            Task(
                description="""
                Attempt to save a thought with invalid data using the create_memory_block tool.
                
                Instructions:
                1. Use the create_memory_block tool with invalid data:
                   - text: "invalid data"
                   - type: "invalid_type"
                2. Return the tool's error response as a JSON string.
                """,
                agent=thinker_agent,
                expected_output="""{
                    "text": "invalid data",
                    "type": "invalid_type"
                }""",
            )
        ],
        verbose=True,
    )

    # Capture Dolt and LlamaIndex state before execution
    repo = Dolt(memory_bank.dolt_db_path)
    commit_count_before = len(repo.log())
    # Get node count before via retriever (querying for a non-existent ID)
    retriever_before = memory_bank.llama_memory.index.as_retriever()
    nodes_before = retriever_before.retrieve("check-non-existent-id-before")
    node_count_before = len(nodes_before)

    # Run the crew (should not raise)
    result_str = crew.kickoff()

    # Parse the JSON string returned by the agent
    if isinstance(result_str, str):
        try:
            result_data = json.loads(result_str)
        except Exception:
            pytest.fail("Could not parse JSON response from tool")
    elif isinstance(result_str, dict):
        result_data = result_str
    else:
        pytest.fail("Unexpected result type from crew.kickoff()")

    assert result_data.get("success") is False, "Tool did not indicate failure for invalid data"

    # Verify that no memory blocks were created
    blocks = memory_bank.query_semantic("invalid", top_k=1)
    assert len(blocks) == 0, "Memory block was created despite invalid data"

    # Verify Dolt state remains unchanged
    commit_count_after = len(repo.log())
    assert commit_count_after == commit_count_before, "Unexpected Dolt commits were created"

    # Verify LlamaIndex state remains unchanged by checking node count again
    retriever_after = memory_bank.llama_memory.index.as_retriever()
    nodes_after = retriever_after.retrieve("check-non-existent-id-after")
    node_count_after = len(nodes_after)
    assert node_count_after == node_count_before, "LlamaIndex node count changed despite error"
