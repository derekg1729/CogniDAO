"""
Migration infrastructure for Dolt database schema and data migrations.

This package provides tools for managing database migrations in a Dolt environment,
following the recommended "Schema Branch and Merge" pattern from DoltHub.
"""

from .runner import MigrationRunner, MigrationError

__all__ = ["MigrationRunner", "MigrationError"]
