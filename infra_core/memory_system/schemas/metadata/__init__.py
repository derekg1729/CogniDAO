"""
Package containing metadata models for different MemoryBlock types.
"""

# Import all metadata modules to ensure all models are registered
# These modules register themselves with the registry
from . import project
from . import task
from . import doc
from . import knowledge
from . import log
from . import epic
from . import bug

# Export all metadata types for convenience
from .project import ProjectMetadata
from .task import TaskMetadata
from .doc import DocMetadata
from .knowledge import KnowledgeMetadata
from .log import LogMetadata
from .epic import EpicMetadata
from .bug import BugMetadata

__all__ = [
    "ProjectMetadata",
    "TaskMetadata",
    "DocMetadata",
    "KnowledgeMetadata",
    "LogMetadata",
    "EpicMetadata",
    "BugMetadata",
    "project",
    "task",
    "doc",
    "knowledge",
    "log",
    "epic",
    "bug",
]
