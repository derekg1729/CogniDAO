CREATE TABLE IF NOT EXISTS memory_blocks (
    id VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    schema_version INT NULL,
    text LONGTEXT NOT NULL,
    state VARCHAR(50) NULL DEFAULT 'draft',
    visibility VARCHAR(50) NULL DEFAULT 'internal',
    block_version INT NULL DEFAULT 1,
    tags JSON NOT NULL,
    metadata JSON NOT NULL,
    links JSON NOT NULL,
    source_file VARCHAR(255) NULL,
    source_uri VARCHAR(255) NULL,
    confidence JSON NULL,
    created_by VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    embedding LONGTEXT NULL
);

CREATE INDEX idx_memory_blocks_type_state_visibility ON memory_blocks (type, state, visibility);

CREATE TABLE IF NOT EXISTS block_links (
    to_id VARCHAR(255) NOT NULL,
    relation VARCHAR(50) NOT NULL
);

CREATE INDEX idx_block_links_to_id ON block_links (to_id);