from langgraph.prebuilt.chat_agent_executor import AgentState
from typing import NotRequired, Annotated
from typing import Literal
from typing_extensions import TypedDict


class Todo(TypedDict):
    """Todo to track."""

    content: str
    status: Literal["pending", "in_progress", "completed"]


def file_reducer(left, right):
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return {**left, **right}


def blocks_reducer(left, right):
    """Reducer for relevant_blocks dictionary."""
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return {**left, **right}


class DeepAgentState(AgentState):
    todos: NotRequired[list[Todo]]
    files: Annotated[NotRequired[dict[str, str]], file_reducer]  # Legacy mock filesystem
    relevant_blocks: Annotated[NotRequired[dict[str, str]], blocks_reducer]  # block_id -> block_title mapping
