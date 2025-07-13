#!/usr/bin/env python3
"""
Integration test for HIL (Human-in-the-Loop) interrupt mechanism.

This test verifies that the HIL checkpoint properly pauses execution
and can be resumed with human input.
"""

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import NodeInterrupt

from src.cogni_image_gen.graph import build_compiled_graph
from src.cogni_image_gen.state_types import ImageFlowState


class TestHILIntegration:
    """Integration tests for HIL interrupt mechanism with checkpointer."""

    @pytest.mark.skip(reason="Requires valid OpenAI API key for integration testing")
    @pytest.mark.asyncio
    async def test_hil_interrupt_with_memory_saver(self, mock_mcp_client):
        """Test HIL interrupt works with MemorySaver checkpointer."""
        # Create memory saver for persistence
        memory_saver = MemorySaver()
        
        # Build graph with checkpointer
        app = await build_compiled_graph(checkpointer=memory_saver)
        
        # Initial state
        initial_state: ImageFlowState = {
            "user_request": "Create a team image with 2 developers",
            "messages": []
        }
        
        # Configuration with thread ID for persistence
        config = {
            "configurable": {"thread_id": "test-hil-interrupt"},
            "recursion_limit": 100
        }
        
        # Run workflow - should interrupt at human_checkpoint
        with pytest.raises(NodeInterrupt) as exc_info:
            await app.ainvoke(initial_state, config=config)
        
        # Verify it's a HIL interrupt with expected payload
        interrupt = exc_info.value
        assert "human_checkpoint" in str(interrupt)
        
        # Get the current state to see what's available for human review
        state_snapshot = await app.aget_state(config)
        current_state = state_snapshot.values
        
        # Verify state has image data for human review
        assert current_state.get("image_url") is not None
        assert current_state.get("user_request") == "Create a team image with 2 developers"
        
        # Simulate human approval
        human_input = {
            "decision": "approve"
        }
        
        # Resume workflow with human decision
        final_result = await app.ainvoke(human_input, config=config)
        
        # Verify workflow completed successfully
        assert final_result["decision"] == "approve"
        assert final_result["assistant_response"] is not None

    @pytest.mark.skip(reason="Requires valid OpenAI API key for integration testing")
    @pytest.mark.asyncio
    async def test_hil_interrupt_with_revision_request(self, mock_mcp_client):
        """Test HIL interrupt handles revision requests properly."""
        # Create memory saver for persistence
        memory_saver = MemorySaver()
        
        # Build graph with checkpointer
        app = await build_compiled_graph(checkpointer=memory_saver)
        
        # Initial state
        initial_state: ImageFlowState = {
            "user_request": "Create a sunset image",
            "messages": []
        }
        
        # Configuration with thread ID for persistence
        config = {
            "configurable": {"thread_id": "test-hil-revision"},
            "recursion_limit": 100
        }
        
        # Run workflow - should interrupt at human_checkpoint
        with pytest.raises(NodeInterrupt):
            await app.ainvoke(initial_state, config=config)
        
        # Simulate human revision request
        human_input = {
            "decision": "revise",
            "planner_feedback": "Make the sunset more dramatic with vibrant colors"
        }
        
        # Resume workflow with revision request
        # This should go back to planner and eventually interrupt again
        with pytest.raises(NodeInterrupt):
            await app.ainvoke(human_input, config=config)
        
        # Get the state after revision cycle
        state_snapshot = await app.aget_state(config)
        current_state = state_snapshot.values
        
        # Should have updated image from the revision
        assert current_state.get("planner_feedback") == "Make the sunset more dramatic with vibrant colors"
        assert current_state.get("attempt", 0) > 0  # Should have incremented attempt counter
        
        # Final approval
        final_approval = {
            "decision": "approve"
        }
        
        final_result = await app.ainvoke(final_approval, config=config)
        assert final_result["decision"] == "approve"

    @pytest.mark.skip(reason="Requires valid OpenAI API key for integration testing")
    @pytest.mark.asyncio
    async def test_hil_interrupt_without_checkpointer_fails(self, mock_mcp_client):
        """Test that HIL interrupt fails gracefully without checkpointer."""
        # Build graph WITHOUT checkpointer
        app = await build_compiled_graph(use_checkpointer=False)
        
        initial_state: ImageFlowState = {
            "user_request": "Create a team image",
            "messages": []
        }
        
        # Should complete without interrupting (since no checkpointer)
        # This demonstrates the checkpointer requirement
        result = await app.ainvoke(initial_state, config={"recursion_limit": 100})
        
        # Without checkpointer, the interrupt gets ignored and workflow continues
        # This should log a warning or handle gracefully
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])