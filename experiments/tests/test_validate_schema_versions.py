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

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        # Mock SCHEMA_VERSIONS for all tests
        cls.patcher = patch(
            "scripts.validate_schema_versions.SCHEMA_VERSIONS",
            {
                "task": 1,
                "project": 1,
                "doc": 1,
                "knowledge": 1,
            },
        )
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        """Clean up test class."""
        cls.patcher.stop()

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
            ("experiments/src/memory_system/schemas/metadata/task.py", "task"),
            ("experiments/src/memory_system/schemas/metadata/project.py", "project"),
            ("experiments/src/memory_system/schemas/metadata/doc.py", "doc"),
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
experiments/src/memory_system/schemas/metadata/task.py
experiments/src/memory_system/schemas/metadata/project.py
some_other_file.py
"""

        result = get_modified_metadata_files()
        self.assertEqual(len(result), 2)
        self.assertIn("experiments/src/memory_system/schemas/metadata/task.py", result)
        self.assertIn("experiments/src/memory_system/schemas/metadata/project.py", result)

    @patch("scripts.validate_schema_versions.get_modified_metadata_files")
    def test_validate_schema_versions_success(self, mock_get_files):
        """Test successful validation when all modified files have version entries."""
        # Mock modified files
        mock_get_files.return_value = [
            "experiments/src/memory_system/schemas/metadata/task.py",
            "experiments/src/memory_system/schemas/metadata/project.py",
        ]

        result = validate_schema_versions()
        self.assertTrue(result)

    @patch("scripts.validate_schema_versions.get_modified_metadata_files")
    def test_validate_schema_versions_failure(self, mock_get_files):
        """Test validation failure when a modified file lacks version entry."""
        # Mock modified files
        mock_get_files.return_value = [
            "experiments/src/memory_system/schemas/metadata/task.py",
            "experiments/src/memory_system/schemas/metadata/new_type.py",
        ]

        result = validate_schema_versions()
        self.assertFalse(result)

    # 🚨 WARNING:
    # If this test fails after moving schemas to 'infra_core', it's working as intended!
    # Update the hardcoded path in scripts/validate_schema_versions.py
    @patch("subprocess.run")
    def test_future_path_structure_does_not_trigger_hook(self, mock_run):
        """Ensure that files outside expected path do not trigger validation (and warn us)."""
        # Simulate a new future path structure
        mock_run.return_value.stdout = """
infra_core/src/memory_system/schemas/metadata/task.py
"""

        result = get_modified_metadata_files()

        # Should be empty since it doesn't match hardcoded "experiments/..."
        self.assertEqual(
            result,
            [],
            "Future path structure was incorrectly matched. This test will fail when code is moved to infra_core, reminding us to update file paths.",
        )


if __name__ == "__main__":
    unittest.main()
