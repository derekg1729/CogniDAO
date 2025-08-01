"""
EDO pattern tools for LangGraph agents.
"""

from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from .logging_utils import get_logger

logger = get_logger(__name__)


@tool
def write_handoff_summary(
    summary: Annotated[str, "Concise 2-3 sentence handoff summary for the next agent"],
    call_id: Annotated[str, InjectedToolCallId]
) -> Command:
    """
    Write a handoff summary to the EDO state for the next agent.
    
    Use this tool to communicate your decision and findings to the next agent
    in the EDO chain. The summary should be concise (2-3 sentences) and 
    actionable.
    
    Args:
        summary: Clear, concise handoff summary for the next agent
        call_id: Tool call ID (automatically injected by LangGraph)
        
    Returns:
        Command object that updates the state
    """
    summary = summary.strip()
    
    if not summary:
        raise ValueError("Handoff summary cannot be empty")
    
    if len(summary) > 500:
        raise ValueError("Handoff summary must be ≤ 500 characters")
    
    logger.info(f"📝 Writing handoff summary: {summary[:100]}...")
    
    return Command(update={
        "edo_handoff_summary": summary,
        "messages": [
            ToolMessage(
                content=f"📝 Handoff summary stored: {summary[:50]}...",
                tool_call_id=call_id
            )
        ]
    })