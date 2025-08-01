"""
Test EDO handoff tool Command pattern implementation.
"""

import pytest
from src.shared_utils.edo_tools import write_handoff_summary


def test_write_handoff_summary_command():
    """Test that write_handoff_summary returns a proper Command object."""
    
    test_summary = "Task completed successfully. Next agent should focus on deployment phase."
    test_call_id = "test_call_123"
    
    # Call the tool function directly
    result = write_handoff_summary.func(test_summary, test_call_id)
    
    # Verify it returns a Command object
    from langgraph.types import Command
    assert isinstance(result, Command)
    
    # Verify the update contains the handoff summary
    assert "edo_handoff_summary" in result.update
    assert result.update["edo_handoff_summary"] == test_summary
    
    # Verify it includes a ToolMessage
    assert "messages" in result.update
    messages = result.update["messages"]
    assert len(messages) == 1
    
    from langchain_core.messages import ToolMessage
    tool_msg = messages[0]
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == test_call_id
    assert "Handoff summary stored" in tool_msg.content


def test_write_handoff_summary_validation():
    """Test validation of handoff summary input."""
    
    test_call_id = "test_call_123"
    
    # Test empty summary
    with pytest.raises(ValueError, match="cannot be empty"):
        write_handoff_summary.func("", test_call_id)
    
    with pytest.raises(ValueError, match="cannot be empty"):
        write_handoff_summary.func("   ", test_call_id)
    
    # Test too long summary
    long_summary = "x" * 501
    with pytest.raises(ValueError, match="must be ≤ 500 characters"):
        write_handoff_summary.func(long_summary, test_call_id)


def test_write_handoff_summary_content():
    """Test that handoff summary content is properly handled."""
    
    test_summary = "  Task analysis complete. Recommend pivot to new approach.  "
    test_call_id = "test_call_123"
    
    result = write_handoff_summary.func(test_summary, test_call_id)
    
    # Verify content is stripped
    assert result.update["edo_handoff_summary"] == test_summary.strip()
    
    # Verify ToolMessage contains truncated preview
    tool_msg = result.update["messages"][0]
    assert "Task analysis complete. Recommend pivot to new app" in tool_msg.content