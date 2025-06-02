"""
LEGACY FILE-BASED DOLT ACCESS (DEPRECATED)

This module contains the legacy file-based Dolt access functions that have been
deprecated due to security vulnerabilities (manual SQL string escaping).

These functions are preserved here for reference only and should NOT be used.
The secure MySQL-based approach in dolt_writer.py and dolt_reader.py should be used instead.

!!! SECURITY WARNING !!!
These functions use manual SQL string escaping which carries SQL injection risks.
They are preserved only for historical reference.
"""

import warnings
import json
import logging
from typing import Optional, Tuple, List, Any, Dict
from pathlib import Path
import sys
from datetime import datetime

# Preserve the legacy imports for completeness
try:
    from doltpy.cli import Dolt
except ImportError:
    Dolt = None
    warnings.warn("doltpy not available - legacy functions will not work")

# --- Path Setup ---
script_dir = Path(__file__).parent
project_root_dir = script_dir.parent.parent.parent
if str(project_root_dir) not in sys.path:
    sys.path.insert(0, str(project_root_dir))

try:
    from infra_core.memory_system.schemas.memory_block import MemoryBlock
    from infra_core.memory_system.schemas.block_property import BlockProperty
except ImportError as e:
    raise ImportError(f"Could not import required schemas: {e}")

logger = logging.getLogger(__name__)

# --- Manual Escaping Functions (INSECURE) ---


def _escape_sql_string(value: Optional[str]) -> str:
    """
    DEPRECATED: Manually escape a string for SQL inclusion.

    WARNING: This is NOT as robust as parameterized queries and carries SQL injection risks.
    """
    warnings.warn("_escape_sql_string is deprecated and insecure", DeprecationWarning)

    if value is None:
        return "NULL"

    import re

    if re.search(r"[\x00\x08\x1a]", value):
        raise ValueError(f"String contains dangerous control characters: {repr(value)}")

    escaped_value = value.replace("'", "''")
    return f"'{escaped_value}'"


def _format_sql_value(value: Optional[Any]) -> str:
    """
    DEPRECATED: Formats a Python value for SQL inclusion.

    WARNING: This is NOT as robust as parameterized queries and carries SQL injection risks.
    """
    warnings.warn("_format_sql_value is deprecated and insecure", DeprecationWarning)

    if value is None:
        return "NULL"
    elif isinstance(value, str):
        return _escape_sql_string(value)
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, bool):
        return "1" if value else "0"
    elif isinstance(value, (list, dict)):
        json_str = json.dumps(value, default=str, ensure_ascii=True)
        return _escape_sql_string(json_str)
    elif isinstance(value, datetime):
        return _escape_sql_string(value.strftime("%Y-%m-%d %H:%M:%S"))
    else:
        return _escape_sql_string(str(value))


# --- Legacy File-Based Functions (DEPRECATED) ---


def legacy_write_memory_block_to_dolt(
    block: MemoryBlock, db_path: str, auto_commit: bool = False, preserve_nulls: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED: Legacy file-based write function with security vulnerabilities.
    Use DoltMySQLWriter.write_memory_block() instead.
    """
    warnings.warn(
        "legacy_write_memory_block_to_dolt() is deprecated and insecure. "
        "Use DoltMySQLWriter.write_memory_block() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def legacy_delete_memory_block_from_dolt(
    block_id: str, db_path: str, auto_commit: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED: Legacy file-based delete function with security vulnerabilities.
    Use DoltMySQLWriter.delete_memory_block() instead.
    """
    warnings.warn(
        "legacy_delete_memory_block_from_dolt() is deprecated and insecure. "
        "Use DoltMySQLWriter.delete_memory_block() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def legacy_discard_working_changes(db_path: str, tables: List[str] = None) -> bool:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLWriter.discard_changes() instead.
    """
    warnings.warn(
        "legacy_discard_working_changes() is deprecated. "
        "Use DoltMySQLWriter.discard_changes() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def legacy_commit_working_changes(
    db_path: str, commit_msg: str, tables: List[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    DEPRECATED: Legacy file-based function.
    Use DoltMySQLWriter.commit_changes() instead.
    """
    warnings.warn(
        "legacy_commit_working_changes() is deprecated. "
        "Use DoltMySQLWriter.commit_changes() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


# --- Legacy File-Based Reader Functions (DEPRECATED) ---


def read_memory_blocks(db_path: str, branch: str = "main") -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based reader function with security vulnerabilities.
    Use DoltMySQLReader.read_memory_blocks() instead.
    """
    warnings.warn(
        "read_memory_blocks() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def read_memory_block(db_path: str, block_id: str, branch: str = "main") -> Optional[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based reader function with security vulnerabilities.
    Use DoltMySQLReader.read_memory_block() instead.
    """
    warnings.warn(
        "read_memory_block() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def read_memory_blocks_by_tags(
    db_path: str, tags: List[str], match_all: bool = True, branch: str = "main"
) -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based reader function with security vulnerabilities.
    Use DoltMySQLReader.read_memory_blocks_by_tags() instead.
    """
    warnings.warn(
        "read_memory_blocks_by_tags() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def read_memory_blocks_from_working_set(db_path: str) -> List[MemoryBlock]:
    """
    DEPRECATED: Legacy file-based reader function with security vulnerabilities.
    Use DoltMySQLReader with appropriate branch instead.
    """
    warnings.warn(
        "read_memory_blocks_from_working_set() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def read_block_properties(db_path: str, block_id: str, branch: str = "main") -> List[BlockProperty]:
    """
    DEPRECATED: Legacy file-based reader function with security vulnerabilities.
    Use DoltMySQLReader.read_block_properties() instead.
    """
    warnings.warn(
        "read_block_properties() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")


def batch_read_block_properties(
    db_path: str, block_ids: List[str], branch: str = "main"
) -> Dict[str, List[BlockProperty]]:
    """
    DEPRECATED: Legacy file-based reader function with security vulnerabilities.
    Use DoltMySQLReader.batch_read_block_properties() instead.
    """
    warnings.warn(
        "batch_read_block_properties() file-based access is deprecated. "
        "Use DoltMySQLReader with a Dolt SQL server instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Implementation preserved for reference - DO NOT USE
    raise NotImplementedError("Legacy file-based functions are disabled for security")
