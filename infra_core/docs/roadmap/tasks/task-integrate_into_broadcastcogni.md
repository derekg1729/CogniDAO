# Task:[Integrate Into BroadcastCogni]
:type: Task
:status: todo
:project: [project-cogni_memory_architecture]
:owner: 

## Description
Integrate the CogniMemoryClient with the BroadcastCogni agent to enable memory-aware context generation, semantic search of past broadcasts, and archiving of approved broadcast content.

## Action Items
- [ ] Update BroadcastCogni to use CogniMemoryClient for context retrieval
- [ ] Add hooks to archive broadcast content with appropriate tags
- [ ] Implement memory-weighted prompt construction for better context
- [ ] Create simple testing workflow to validate integration
- [ ] Document integration patterns for other agents
- [ ] Add logging for memory operations in agent workflows

## Deliverables
1. Integration code in BroadcastCogni:
   - Memory context retrieval hooks
   - Broadcast content archiving logic
   - Memory-weighted prompt construction

2. A sample integration workflow in `examples/memory_broadcast_integration.py`

3. Documentation on integration patterns:
   - How to use memory in agents
   - Best practices for memory operations
   - Example workflows

4. Logging and monitoring of memory operations

## Test Criteria
- [ ] Test memory context retrieval:
```python
def test_memory_context_retrieval():
    # Setup BroadcastCogni with memory
    broadcast_agent = BroadcastCogni(
        memory_client=CogniMemoryClient("./test_chroma")
    )
    
    # Generate context for a broadcast
    context = broadcast_agent.generate_context("user question about previous broadcasts")
    
    # Verify memory is included in context
    assert len(context) > 0
    assert any("memory_context" in section for section in context)
```

- [ ] Test broadcast archiving:
```python
def test_broadcast_archiving():
    # Setup with test memory
    client = CogniMemoryClient("./test_chroma")
    broadcast_agent = BroadcastCogni(memory_client=client)
    
    # Create a test broadcast
    broadcast = {
        "text": "This is a test broadcast with important info",
        "approved": True,
        "timestamp": "2023-06-15T12:00:00Z"
    }
    
    # Archive broadcast
    broadcast_agent.archive_broadcast(broadcast)
    
    # Query for the broadcast content
    results = client.query("test broadcast important info")
    
    # Should find the broadcast in memory
    assert len(results.blocks) > 0
    assert any("test broadcast" in block.text for block in results.blocks)
```

- [ ] Test memory-weighted prompt construction:
```python
def test_memory_weighted_prompt():
    # Setup with pre-populated memory
    client = CogniMemoryClient("./test_chroma")
    broadcast_agent = BroadcastCogni(memory_client=client)
    
    # Generate a prompt with memory weighting
    prompt = broadcast_agent._construct_prompt_with_memory(
        query="user asking about recent decisions"
    )
    
    # Verify memory context is included with weighting
    assert "recent_memory" in prompt
    assert "relevant_context" in prompt
    assert len(prompt["recent_memory"]) > 0
```

- [ ] Verify logging of memory operations
- [ ] Test with representative agent workflows
- [ ] Validate performance impact on agent operations

## Notes
- Focus on minimal, high-value integration points first
- Ensure memory operations don't block agent responsiveness
- Consider asynchronous archiving of new content
- Document the integration pattern for reuse with other agents

## Dependencies
- Completed CogniMemoryClient from task-build_cogni_memory_client
- Existing BroadcastCogni agent implementation 