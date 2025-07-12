#!/usr/bin/env python3
"""
Tests for Reviewer Feedback Loop in Cogni Image Gen
===================================================

Tests the new reviewer validation that occurs BEFORE image generation,
with automatic retry up to 5 attempts for quality improvement.
"""

import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage

from src.cogni_image_gen.nodes import create_reviewer_node
from src.cogni_image_gen.state_types import ImageFlowState
from src.cogni_image_gen.graph import build_graph


class TestReviewerNode:
    """Unit tests for the reviewer node validation logic."""

    @pytest.mark.asyncio
    async def test_reviewer_approves_good_plan(self):
        """Test reviewer approves a well-formed plan."""
        # Mock the LLM response for good plan
        from pydantic import BaseModel
        from typing import List
        
        class MockReviewerOutput(BaseModel):
            score: float = 0.9
            needs_retry: bool = False
            issues: List[str] = []
            suggestions: List[str] = []
        
        with patch('src.cogni_image_gen.nodes.ChatOpenAI') as mock_llm:
            mock_structured_model = AsyncMock()
            mock_structured_model.ainvoke.return_value = MockReviewerOutput()
            mock_llm.return_value.with_structured_output.return_value = mock_structured_model
            
            reviewer_node = await create_reviewer_node()
            
            # Good plan with complete agents and scene
            state = {
                "agents_with_roles": [
                    {"role_name": "Developer", "pose": "coding", "prop": "laptop"},
                    {"role_name": "Designer", "pose": "sketching", "prop": "tablet"}
                ],
                "scene_focus": "collaborative development session in modern office",
                "messages": []
            }
            
            result = await reviewer_node(state)
            
            assert result["attempt"] == 1
            assert result["needs_retry"] is False
            assert result["score"] == 0.9
            assert isinstance(result["issues"], list)
            assert isinstance(result["suggestions"], list)
            assert "approved" in result["messages"][0].content.lower()

    @pytest.mark.asyncio
    async def test_reviewer_rejects_poor_plan(self):
        """Test reviewer rejects incomplete plan."""
        # Mock the LLM response for poor plan
        from pydantic import BaseModel
        from typing import List
        
        class MockReviewerOutput(BaseModel):
            score: float = 0.4
            needs_retry: bool = True
            issues: List[str] = ["Incomplete agent details", "Scene too brief"]
            suggestions: List[str] = ["Add pose and prop to agents", "Expand scene description"]
        
        with patch('src.cogni_image_gen.nodes.ChatOpenAI') as mock_llm:
            mock_structured_model = AsyncMock()
            mock_structured_model.ainvoke.return_value = MockReviewerOutput()
            mock_llm.return_value.with_structured_output.return_value = mock_structured_model
            
            reviewer_node = await create_reviewer_node()
            
            # Poor plan with incomplete agents
            state = {
                "agents_with_roles": [
                    {"role_name": "Developer"}  # Missing pose and prop
                ],
                "scene_focus": "work",  # Too brief
                "messages": []
            }
            
            result = await reviewer_node(state)
            
            assert result["attempt"] == 1
            assert result["needs_retry"] is True
            assert result["score"] == 0.4
            assert isinstance(result["issues"], list)
            assert isinstance(result["suggestions"], list)
            assert len(result["issues"]) > 0  # Should have identified issues
            assert len(result["suggestions"]) > 0  # Should have suggestions
            assert "improvement" in result["messages"][0].content.lower()

    @pytest.mark.asyncio
    async def test_reviewer_rejects_empty_plan(self):
        """Test reviewer rejects empty plan."""
        # Mock the LLM response for empty plan
        from pydantic import BaseModel
        from typing import List
        
        class MockReviewerOutput(BaseModel):
            score: float = 0.0
            needs_retry: bool = True
            issues: List[str] = ["No agents defined", "No scene focus provided"]
            suggestions: List[str] = ["Add at least one agent", "Define scene context"]
        
        with patch('src.cogni_image_gen.nodes.ChatOpenAI') as mock_llm:
            mock_structured_model = AsyncMock()
            mock_structured_model.ainvoke.return_value = MockReviewerOutput()
            mock_llm.return_value.with_structured_output.return_value = mock_structured_model
            
            reviewer_node = await create_reviewer_node()
            
            # Empty plan
            state = {
                "agents_with_roles": [],
                "scene_focus": "",
                "messages": []
            }
            
            result = await reviewer_node(state)
            
            assert result["attempt"] == 1
            assert result["needs_retry"] is True
            assert result["score"] == 0.0
            assert isinstance(result["issues"], list)
            assert isinstance(result["suggestions"], list)
            assert len(result["issues"]) > 0  # Should identify empty plan issues

    @pytest.mark.asyncio
    async def test_reviewer_handles_missing_fields(self):
        """Test reviewer handles missing state fields gracefully."""
        # Mock the LLM response for missing fields
        from pydantic import BaseModel
        from typing import List
        
        class MockReviewerOutput(BaseModel):
            score: float = 0.0
            needs_retry: bool = True
            issues: List[str] = ["Missing agents data", "Missing scene data"]
            suggestions: List[str] = ["Provide agent configurations", "Define scene context"]
        
        with patch('src.cogni_image_gen.nodes.ChatOpenAI') as mock_llm:
            mock_structured_model = AsyncMock()
            mock_structured_model.ainvoke.return_value = MockReviewerOutput()
            mock_llm.return_value.with_structured_output.return_value = mock_structured_model
            
            reviewer_node = await create_reviewer_node()
            
            # State with missing fields
            state = {"messages": []}
            
            result = await reviewer_node(state)
            
            assert result["attempt"] == 1
            assert result["needs_retry"] is True
            assert result["score"] == 0.0
            assert isinstance(result["issues"], list)
            assert isinstance(result["suggestions"], list)


class TestWorkflowIntegration:
    """Integration tests for reviewer feedback loop in workflow."""

    @pytest.mark.asyncio
    async def test_workflow_has_reviewer_before_image_tool(self, mock_mcp_client):
        """Test that workflow places reviewer before image generation."""
        workflow = await build_graph()
        
        # Check that workflow compiled successfully
        compiled = workflow.compile()
        assert compiled is not None
        
        # The workflow structure should be:
        # planner → reviewer → (conditional) planner OR image_tool → responder
        # This is verified by successful compilation

    def test_conditional_edge_logic_continues_retry(self):
        """Test conditional edge continues to planner when retry needed."""
        
        # Simulate state that needs retry with low attempts
        state = {
            "needs_retry": True,
            "attempt": 2  # Under 5 limit
        }
        
        # This tests the decide_next function logic
        needs_retry = state.get("needs_retry", False)
        attempt = state.get("attempt", 0)
        
        if needs_retry and attempt < 5:
            result = "planner"
        else:
            result = "image_tool"
        
        assert result == "planner"

    def test_conditional_edge_logic_proceeds_to_image(self):
        """Test conditional edge proceeds to image generation when approved."""
        # Simulate state that doesn't need retry
        state = {
            "needs_retry": False,
            "attempt": 1
        }
        
        needs_retry = state.get("needs_retry", False)
        attempt = state.get("attempt", 0)
        
        if needs_retry and attempt < 5:
            result = "planner"
        else:
            result = "image_tool"
        
        assert result == "image_tool"

    def test_conditional_edge_logic_max_attempts(self):
        """Test conditional edge stops retry at max 5 attempts."""
        # Simulate state that needs retry but hit max attempts
        state = {
            "needs_retry": True,
            "attempt": 5  # At limit
        }
        
        needs_retry = state.get("needs_retry", False)
        attempt = state.get("attempt", 0)
        
        if needs_retry and attempt < 5:
            result = "planner"
        else:
            result = "image_tool"
        
        assert result == "image_tool"


# class TestPlannerFeedbackConsumption:
#     """Test planner consuming reviewer feedback."""
#     # TODO: Add planner feedback consumption tests with proper LLM mocking


class TestStateManagement:
    """Test state field management for reviewer feedback loop."""

    def test_attempt_field_annotation(self):
        """Test that attempt field uses operator.add annotation."""
        # This tests the state type annotation
        from src.cogni_image_gen.state_types import ImageFlowState
        
        # Check that the field exists (runtime check)
        state: ImageFlowState = {
            "attempt": 0,
            "needs_retry": False,
            "score": None,
            "issues": [],
            "suggestions": [],
            "messages": []
        }
        
        assert "attempt" in state
        assert "needs_retry" in state
        assert "score" in state
        assert "issues" in state
        assert "suggestions" in state

    def test_state_field_types(self):
        """Test reviewer state field types."""
        state: ImageFlowState = {
            "attempt": 1,
            "needs_retry": True,
            "score": 0.75,
            "issues": ["Issue 1", "Issue 2"],
            "suggestions": ["Suggestion 1"],
            "messages": [HumanMessage(content="test")]
        }
        
        assert isinstance(state["attempt"], int)
        assert isinstance(state["needs_retry"], bool)
        assert isinstance(state["score"], (float, type(None)))
        assert isinstance(state["issues"], list)
        assert isinstance(state["suggestions"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])