"""Schema migration 8: independently executable SQL."""

SQL = r"""
CREATE TABLE IF NOT EXISTS story_atlases (
    atlas_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    atlas_version INTEGER NOT NULL,
    parent_atlas_id TEXT REFERENCES story_atlases(atlas_id),
    base_event_seq INTEGER NOT NULL,
    base_projection_hash TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL,
    effective_content_sha256 TEXT NOT NULL DEFAULT '',
    registry_hash TEXT NOT NULL DEFAULT '',
    config_hash TEXT NOT NULL DEFAULT '',
    analyzer_versions_hash TEXT NOT NULL DEFAULT '',
    horizon_id TEXT,
    horizon_hash TEXT NOT NULL DEFAULT '',
    artifact_root TEXT NOT NULL,
    manifest_path TEXT NOT NULL,
    artifact_manifest_sha256 TEXT NOT NULL,
    atlas_content_hash TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    readiness_status TEXT NOT NULL DEFAULT 'READY_WITH_GAPS',
    readiness_json TEXT NOT NULL DEFAULT '{}',
    author_accepted INTEGER NOT NULL DEFAULT 0,
    accepted_by TEXT,
    accepted_at TEXT,
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, edition_id, atlas_version)
);
CREATE INDEX IF NOT EXISTS idx_story_atlases_scope
    ON story_atlases(book_id, edition_id, status, atlas_version DESC);

CREATE TABLE IF NOT EXISTS story_atlas_usage (
    usage_id TEXT PRIMARY KEY,
    atlas_id TEXT NOT NULL REFERENCES story_atlases(atlas_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    atlas_version INTEGER NOT NULL DEFAULT 1,
    atlas_hash TEXT NOT NULL DEFAULT '',
    batch_id TEXT,
    handoff_id TEXT,
    usage_kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_story_atlas_usage_atlas
    ON story_atlas_usage(atlas_id, created_at DESC);

CREATE TABLE IF NOT EXISTS story_atlas_actions (
    action_id TEXT PRIMARY KEY,
    atlas_id TEXT NOT NULL REFERENCES story_atlases(atlas_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    actor TEXT NOT NULL DEFAULT 'AUTHOR',
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_story_atlas_actions_atlas
    ON story_atlas_actions(atlas_id, created_at DESC);

CREATE TABLE IF NOT EXISTS batch_working_projections (
    batch_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    atlas_id TEXT REFERENCES story_atlases(atlas_id),
    atlas_version INTEGER,
    atlas_hash TEXT NOT NULL DEFAULT '',
    horizon_hash TEXT NOT NULL DEFAULT '',
    base_event_seq INTEGER NOT NULL,
    base_projection_hash TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL DEFAULT '',
    input_effective_content_sha256 TEXT NOT NULL DEFAULT '',
    registry_hash TEXT NOT NULL DEFAULT '',
    config_hash TEXT NOT NULL DEFAULT '',
    author_directives_hash TEXT NOT NULL DEFAULT '',
    metric_bundle_hash TEXT NOT NULL DEFAULT '',
    current_projection_hash TEXT NOT NULL,
    current_chapter_ordinal INTEGER NOT NULL,
    target_chapter_count INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL DEFAULT 5,
    checkpoint_interval INTEGER NOT NULL DEFAULT 10,
    status TEXT NOT NULL DEFAULT 'PLANNED',
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_batch_working_projections_scope
    ON batch_working_projections(book_id, edition_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS batch_chunk_states (
    chunk_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batch_working_projections(batch_id),
    chunk_order INTEGER NOT NULL,
    start_chapter_ordinal INTEGER NOT NULL,
    end_chapter_ordinal INTEGER NOT NULL,
    input_projection_hash TEXT NOT NULL,
    output_projection_hash TEXT NOT NULL,
    provisional_state_hash TEXT NOT NULL DEFAULT '',
    boundary_hash TEXT NOT NULL DEFAULT '',
    contract_ids_json TEXT NOT NULL DEFAULT '[]',
    validation_report_ids_json TEXT NOT NULL DEFAULT '[]',
    failure_reason TEXT,
    input_state_json TEXT NOT NULL DEFAULT '{}',
    output_state_json TEXT NOT NULL DEFAULT '{}',
    validator_summary_json TEXT NOT NULL DEFAULT '{}',
    atlas_refresh_required INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PLANNED',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(batch_id, chunk_order)
);
CREATE INDEX IF NOT EXISTS idx_batch_chunk_states_order
    ON batch_chunk_states(batch_id, chunk_order);

CREATE TABLE IF NOT EXISTS batch_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batch_working_projections(batch_id),
    chapter_ordinal INTEGER NOT NULL,
    projection_hash TEXT NOT NULL,
    atlas_version INTEGER,
    atlas_hash TEXT NOT NULL DEFAULT '',
    horizon_hash TEXT NOT NULL DEFAULT '',
    rhythm_snapshot_id TEXT,
    report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_batch_checkpoints_order
    ON batch_checkpoints(batch_id, chapter_ordinal DESC);

CREATE TABLE IF NOT EXISTS story_atlas_review_queue (
    review_id TEXT PRIMARY KEY,
    atlas_id TEXT NOT NULL REFERENCES story_atlases(atlas_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_story_atlas_review_queue
    ON story_atlas_review_queue(book_id, edition_id, status, created_at DESC);
"""



__all__ = ["SQL"]
