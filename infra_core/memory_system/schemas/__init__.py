"""
Schema package for the Memory System.

This package provides the data models for the memory system,
including the core MemoryBlock class and metadata schemas for
different block types.
"""

# Import core models
from .memory_block import MemoryBlock
from .common import BlockLink, ConfidenceScore, RelationType, NodeSchemaRecord

# Import registry
from .registry import (
    get_metadata_model,
    get_all_metadata_models,
    validate_metadata
)

# Import all metadata models
from .metadata import (
    ProjectMetadata,
    TaskMetadata,
    DocMetadata,
    KnowledgeMetadata
)

# For backward compatibility
TYPE_METADATA_MAP = get_all_metadata_models()

# Export key types
__all__ = [
    'MemoryBlock',
    'BlockLink',
    'ConfidenceScore',
    'RelationType',
    'NodeSchemaRecord',
    'get_metadata_model',
    'get_all_metadata_models',
    'validate_metadata',
    'ProjectMetadata',
    'TaskMetadata', 
    'DocMetadata',
    'KnowledgeMetadata',
    'TYPE_METADATA_MAP',
] 