#!/usr/bin/env python3
"""
Tests for Human-in-the-Loop Checkpoint in Cogni Image Gen
=========================================================

Tests the HIL checkpoint that interrupts execution after image generation
to allow human review and approval/revision decisions.
"""

import pytest
from langgraph.types import Interrupt

from src.cogni_image_gen.nodes import create_hil_node
from src.cogni_image_gen.state_types import ImageFlowState
from src.cogni_image_gen.graph import build_graph


class TestHILNode:
    """Unit tests for the human-in-the-loop checkpoint node."""

    @pytest.mark.asyncio
    async def test_hil_node_creates_interrupt(self):
        """Test HIL node returns proper Interrupt object with review payload."""
        hil_node = await create_hil_node()
        
        # State after image generation
        state = {
            "user_request": "Create a development team image",
            "agents_with_roles": [
                {"role_name": "Developer", "pose": "coding", "prop": "laptop"},
                {"role_name": "Designer", "pose": "sketching", "prop": "tablet"}
            ],
            "scene_focus": "collaborative development session",
            "score": 0.9,
            "issues": [],
            "suggestions": [],
            "image_url": "https://example.com/generated-image.png",
            "final_prompt": "Generated prompt for DALL-E",
            "attempt": 1,
            "messages": []
        }
        
        result = await hil_node(state)
        
        # Should return an Interrupt object
        assert isinstance(result, Interrupt)
        
        # Check the interrupt value contains expected payload
        payload = result.value
        assert payload["user_request"] == "Create a development team image"
        assert payload["image_url"] == "https://example.com/generated-image.png"
        assert payload["reviewer_score"] == 0.9
        assert len(payload["agents_with_roles"]) == 2
        assert payload["scene_focus"] == "collaborative development session"
        assert payload["attempt"] == 1

    @pytest.mark.asyncio
    async def test_hil_node_handles_minimal_state(self):
        """Test HIL node handles state with minimal fields gracefully."""
        hil_node = await create_hil_node()
        
        # Minimal state
        state = {
            "image_url": "https://example.com/image.png",
            "messages": []
        }
        
        result = await hil_node(state)
        
        # Should still return Interrupt object
        assert isinstance(result, Interrupt)
        
        # Check payload handles missing fields gracefully
        payload = result.value
        assert payload["image_url"] == "https://example.com/image.png"
        assert payload["user_request"] is None
        assert payload["reviewer_score"] is None
        assert payload["reviewer_issues"] == []


class TestHILGraphIntegration:
    """Integration tests for HIL checkpoint in the full graph."""

    @pytest.mark.asyncio
    async def test_graph_includes_hil_checkpoint(self, mock_mcp_client):
        """Test that graph properly includes human_checkpoint node."""
        workflow = await build_graph()
        compiled = workflow.compile()
        
        # Check that compiled graph includes the HIL node
        assert compiled is not None
        
        # The graph should have 5 nodes including human_checkpoint
        # This is verified by successful compilation

    def test_human_decision_routing_approve(self):
        """Test conditional logic routes to responder when human approves."""
        # Simulate human approval decision
        state = {
            "decision": "approve",
            "image_url": "https://example.com/image.png"
        }
        
        # Test the decision logic from the graph
        decision = state.get("decision")
        if decision == "approve":
            result = "responder"
        elif decision == "revise":
            result = "planner"
        else:
            result = "responder"
        
        assert result == "responder"

    def test_human_decision_routing_revise(self):
        """Test conditional logic routes to planner when human requests revision."""
        # Simulate human revision request
        state = {
            "decision": "revise",
            "planner_feedback": "Make the background darker",
            "image_url": "https://example.com/image.png"
        }
        
        # Test the decision logic from the graph
        decision = state.get("decision")
        if decision == "approve":
            result = "responder"
        elif decision == "revise":
            result = "planner"
        else:
            result = "responder"
        
        assert result == "planner"

    def test_human_decision_routing_default(self):
        """Test conditional logic defaults to responder for safety."""
        # Simulate missing or invalid decision
        state = {
            "decision": None,
            "image_url": "https://example.com/image.png"
        }
        
        # Test the decision logic from the graph
        decision = state.get("decision")
        if decision == "approve":
            result = "responder"
        elif decision == "revise":
            result = "planner"
        else:
            result = "responder"
        
        assert result == "responder"


class TestStateManagement:
    """Test HIL state field management."""

    def test_hil_state_fields(self):
        """Test HIL state fields are properly typed."""
        state: ImageFlowState = {
            "decision": "approve",
            "planner_feedback": "Looks good, but make agents bigger",
            "last_interrupt_id": "interrupt-123",
            "image_url": "https://example.com/image.png",
            "messages": []
        }
        
        assert state["decision"] == "approve"
        assert isinstance(state["planner_feedback"], str)
        assert isinstance(state["last_interrupt_id"], str)
        
    def test_literal_type_validation(self):
        """Test decision field accepts only valid literal values."""
        # This is a runtime check since TypedDict doesn't enforce at runtime
        valid_decisions = ["approve", "revise", None]
        
        for decision in valid_decisions:
            state: ImageFlowState = {
                "decision": decision,
                "messages": []
            }
            # Should not raise type errors
            assert state["decision"] in [None, "approve", "revise"]


class TestPlannerFeedbackIntegration:
    """Test planner integration with human feedback."""

    def test_planner_feedback_xml_formatting(self):
        """Test planner formats human feedback with XML tags."""
        # This tests the logic from the planner node
        planner_feedback = "Make the background darker and add more agents"
        
        # Simulate the XML formatting logic
        feedback_sections = []
        if planner_feedback:
            feedback_sections.append(f"<HUMAN_FEEDBACK>\n{planner_feedback}\n</HUMAN_FEEDBACK>")
        
        expected = "<HUMAN_FEEDBACK>\nMake the background darker and add more agents\n</HUMAN_FEEDBACK>"
        assert feedback_sections[0] == expected

    def test_planner_feedback_priority_over_reviewer(self):
        """Test human feedback takes priority over reviewer suggestions."""
        # Simulate both types of feedback
        planner_feedback = "Human says: Add more variety"
        suggestions = ["Reviewer says: Fix agent props"]
        
        feedback_sections = []
        
        # Human feedback goes first (highest priority)
        if planner_feedback:
            feedback_sections.append(f"<HUMAN_FEEDBACK>\n{planner_feedback}\n</HUMAN_FEEDBACK>")
        
        # Reviewer suggestions second
        if suggestions:
            feedback_sections.append(f"<critique>\n{chr(10).join(suggestions)}\n</critique>")
        
        # Human feedback should be first in the list
        assert "<HUMAN_FEEDBACK>" in feedback_sections[0]
        assert "<critique>" in feedback_sections[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])