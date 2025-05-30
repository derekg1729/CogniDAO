"""
Test utilities for SQLLinkManager tests.
"""


def add_parent_child_columns_to_db(db_path):
    """Add parent_id and has_children columns to the test database."""
    from doltpy.cli import Dolt

    repo = Dolt(db_path)

    try:
        # Add parent_id and has_children columns
        migration_query = """
        ALTER TABLE memory_blocks 
        ADD COLUMN parent_id VARCHAR(36) DEFAULT NULL,
        ADD COLUMN has_children BOOLEAN DEFAULT FALSE;
        """
        repo.sql(query=migration_query)

        # Add foreign key constraint
        fk_query = """
        ALTER TABLE memory_blocks
        ADD CONSTRAINT fk_memory_blocks_parent
        FOREIGN KEY (parent_id) REFERENCES memory_blocks(id) ON DELETE CASCADE;
        """
        repo.sql(query=fk_query)

        # Add indexes for performance
        index_queries = [
            "CREATE INDEX idx_memory_blocks_parent_id ON memory_blocks (parent_id);",
            "CREATE INDEX idx_memory_blocks_has_children ON memory_blocks (has_children);",
        ]
        for index_query in index_queries:
            repo.sql(query=index_query)

    except Exception as e:
        # Columns might already exist, ignore errors
        if "already exists" not in str(e).lower():
            raise
