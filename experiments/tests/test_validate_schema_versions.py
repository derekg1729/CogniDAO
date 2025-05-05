#!/usr/bin/env python3
"""
Tests for validate_schema_versions.py pre-commit hook.
"""

import sys
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch

# Add project root to path before local imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.validate_schema_versions import (  # noqa: E402
    get_modified_metadata_files,
    get_block_type_from_path,
    validate_schema_versions,
)


class TestValidateSchemaVersions(unittest.TestCase):
    """Tests for schema version validation."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.metadata_dir = (
            Path(self.temp_dir) / "experiments" / "src" / "memory_system" / "schemas" / "metadata"
        )
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)

    def test_get_block_type_from_path(self):
        """Test extracting block type from file path."""
        test_cases = [
            ("infra_core/memorysystem/schemas/metadata/task.py", "task"),
            ("infra_core/memorysystem/schemas/metadata/project.py", "project"),
            ("infra_core/memorysystem/schemas/metadata/doc.py", "doc"),
        ]

        for path, expected in test_cases:
            with self.subTest(path=path):
                result = get_block_type_from_path(path)
                self.assertEqual(result, expected)

    @patch("subprocess.run")
    def test_get_modified_metadata_files(self, mock_run):
        """Test detection of modified metadata files."""
        # Mock git diff output
        mock_run.return_value.stdout = """
infra_core/memorysystem/schemas/metadata/task.py
infra_core/memorysystem/schemas/metadata/project.py
some_other_file.py
"""

        result = get_modified_metadata_files()
        self.assertEqual(len(result), 2)
        self.assertIn("infra_core/memorysystem/schemas/metadata/task.py", result)
        self.assertIn("infra_core/memorysystem/schemas/metadata/project.py", result)

    @patch("scripts.validate_schema_versions.get_modified_metadata_files")
    @patch("scripts.validate_schema_versions.get_staged_schema_versions")
    def test_validate_schema_versions_success(self, mock_get_versions, mock_get_files):
        """Test successful validation when all modified files have version entries."""
        # Mock modified files
        mock_get_files.return_value = [
            "infra_core/memorysystem/schemas/metadata/task.py",
            "infra_core/memorysystem/schemas/metadata/project.py",
        ]
        # Mock the versions read from the staged registry.py
        # Assume versions were correctly incremented relative to BASELINE_VERSIONS in the script
        # BASELINE_VERSIONS = {"base": 1, "project": 1, "task": 1, "doc": 1, "knowledge": 1, "log": 2}
        mock_get_versions.return_value = {
            "base": 1,  # Not modified, version doesn't matter
            "project": 2,  # Modified, version > baseline (1) -> OK
            "task": 2,  # Modified, version > baseline (1) -> OK
            "doc": 1,  # Not modified
            "knowledge": 1,  # Not modified
            "log": 2,  # Not modified
        }

        result = validate_schema_versions()
        self.assertTrue(result)

    @patch("scripts.validate_schema_versions.get_modified_metadata_files")
    @patch("scripts.validate_schema_versions.get_staged_schema_versions")
    def test_validate_schema_versions_failure(self, mock_get_versions, mock_get_files):
        """Test validation failure when a modified file lacks version entry."""
        # Mock modified files
        mock_get_files.return_value = [
            "infra_core/memorysystem/schemas/metadata/task.py",
            "infra_core/memorysystem/schemas/metadata/new_type.py",
        ]
        # Mock versions read from staged registry.py (missing 'new_type')
        mock_get_versions.return_value = {
            "base": 1,
            "project": 1,
            "task": 2,
            "doc": 1,
            "knowledge": 1,
            "log": 2,
        }

        result = validate_schema_versions()
        self.assertFalse(result)  # Should fail because new_type is missing from versions

    @patch("scripts.validate_schema_versions.get_modified_metadata_files")
    @patch("scripts.validate_schema_versions.get_staged_schema_versions")
    def test_validate_base_schema_without_version_increment(
        self, mock_get_versions, mock_get_files
    ):
        """Test validation failure when base.py is modified but version not incremented."""
        # Mock base.py being modified
        mock_get_files.return_value = [
            "infra_core/memorysystem/schemas/metadata/base.py",
        ]
        # Mock versions where 'base' is NOT incremented relative to BASELINE_VERSIONS
        # BASELINE_VERSIONS has base: 1, so staged version 1 should fail
        mock_get_versions.return_value = {
            "base": 1,  # Modified, but version <= baseline (1) -> FAIL
            "project": 1,
            "task": 1,
            "doc": 1,
            "knowledge": 1,
            "log": 2,
        }

        # We should detect that base.py is modified but its version is still 1 in SCHEMA_VERSIONS
        with patch("scripts.validate_schema_versions.logger") as mock_logger:
            result = validate_schema_versions()
            # The validation should fail
            self.assertFalse(result)
            # Logger should have an error about base schema needing version bump
            mock_logger.error.assert_called()

    # 🚨 WARNING:
    # If this test fails after moving schemas to 'legacy_logseq', it's working as intended!
    # Update the hardcoded path in scripts/validate_schema_versions.py
    @patch("subprocess.run")
    def test_future_path_structure_does_not_trigger_hook(self, mock_run):
        """Ensure that files outside expected path do not trigger validation (and warn us)."""
        # Simulate a new future path structure
        mock_run.return_value.stdout = """
legacy_logseq/src/memory_system/schemas/metadata/task.py
"""

        result = get_modified_metadata_files()

        # Should be empty since it doesn't match hardcoded "experiments/..."
        self.assertEqual(
            result,
            [],
            "Future path structure was incorrectly matched. This test will fail when code is moved to legacy_logseq, reminding us to update file paths.",
        )


if __name__ == "__main__":
    unittest.main()
