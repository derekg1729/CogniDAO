CREATE TABLE IF NOT EXISTS memory_blocks (
    id VARCHAR(255) PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    schema_version INT NULL,
    text LONGTEXT NOT NULL,
    state VARCHAR(50) NULL DEFAULT 'draft',
    visibility VARCHAR(50) NULL DEFAULT 'internal',
    block_version INT NULL DEFAULT 1,
    parent_id VARCHAR(255) NULL,
    has_children BOOLEAN NOT NULL DEFAULT False,
    tags JSON NOT NULL,
    metadata JSON NOT NULL,
    source_file VARCHAR(255) NULL,
    source_uri VARCHAR(255) NULL,
    confidence JSON NULL,
    created_by VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    embedding LONGTEXT NULL,
    CONSTRAINT chk_valid_state CHECK (state IN ('draft', 'published', 'archived')),
    CONSTRAINT chk_valid_visibility CHECK (visibility IN ('internal', 'public', 'restricted')),
    CONSTRAINT chk_block_version_positive CHECK (block_version > 0)
);

CREATE INDEX idx_memory_blocks_type_state_visibility ON memory_blocks (type, state, visibility);

CREATE TABLE IF NOT EXISTS block_links (
    to_id VARCHAR(255) NOT NULL,
    from_id VARCHAR(255) NOT NULL,
    relation VARCHAR(50) NOT NULL,
    priority INT NULL DEFAULT 0,
    link_metadata JSON NULL,
    created_by VARCHAR(255) NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (from_id, to_id, relation)
);

CREATE INDEX idx_block_links_to_id ON block_links (to_id);

CREATE TABLE IF NOT EXISTS block_type_schema (
    node_type VARCHAR(255) NOT NULL,
    schema_version INT NOT NULL,
    json_schema JSON NOT NULL,
    created_at VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS block_properties (
    block_id VARCHAR(255) NOT NULL,
    property_name VARCHAR(255) NOT NULL,
    property_value VARCHAR(255) NOT NULL,
    property_type VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (block_id, property_name)
);

CREATE TABLE IF NOT EXISTS block_proofs (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    block_id VARCHAR(255) NOT NULL,
    commit_hash VARCHAR(255) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    timestamp DATETIME NOT NULL,
    INDEX block_id_idx (block_id)
);