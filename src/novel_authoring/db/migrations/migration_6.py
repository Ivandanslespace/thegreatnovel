"""Schema migration 6: independently executable SQL."""

SQL = r"""
ALTER TABLE candidate_plans ADD COLUMN metric_run_id TEXT;
ALTER TABLE candidate_plans ADD COLUMN metric_bundle_hash TEXT;
ALTER TABLE candidate_plans ADD COLUMN rhythm_snapshot_id TEXT;
ALTER TABLE candidate_plans ADD COLUMN registry_hash TEXT;
ALTER TABLE candidate_plans ADD COLUMN config_hash TEXT;
ALTER TABLE candidate_plans ADD COLUMN stale_reason TEXT;

ALTER TABLE chapter_contracts ADD COLUMN metric_run_id TEXT;
ALTER TABLE chapter_contracts ADD COLUMN metric_bundle_hash TEXT;
ALTER TABLE chapter_contracts ADD COLUMN rhythm_snapshot_id TEXT;
ALTER TABLE chapter_contracts ADD COLUMN registry_hash TEXT;
ALTER TABLE chapter_contracts ADD COLUMN config_hash TEXT;
ALTER TABLE chapter_contracts ADD COLUMN stale_reason TEXT;

CREATE TABLE IF NOT EXISTS chapter_features (
    feature_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    effective_content_sha256 TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    planned_primary_function TEXT,
    realized_primary_function TEXT,
    function_confidence REAL,
    emotional_intensity_band TEXT,
    emotional_confidence REAL,
    title_raw TEXT NOT NULL DEFAULT '',
    normalized_title TEXT NOT NULL,
    title_fingerprint TEXT NOT NULL,
    opening_excerpt_raw TEXT NOT NULL,
    opening_excerpt_prose TEXT NOT NULL,
    opening_fingerprint_raw TEXT NOT NULL,
    opening_fingerprint_prose TEXT NOT NULL,
    opening_mode TEXT,
    ending_excerpt_raw TEXT NOT NULL,
    ending_excerpt_prose TEXT NOT NULL,
    ending_fingerprint_raw TEXT NOT NULL,
    ending_fingerprint_prose TEXT NOT NULL,
    ending_mode TEXT,
    extractor_kind TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, edition_id, chapter_id, effective_content_sha256, analyzer_version, config_hash)
);
CREATE INDEX IF NOT EXISTS idx_chapter_features_edition_ordinal
    ON chapter_features(book_id, edition_id, chapter_id, status);

CREATE TABLE IF NOT EXISTS rhythm_diagnostic_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    as_of_chapter INTEGER NOT NULL,
    as_of_event_seq INTEGER NOT NULL,
    projection_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    analyzer_versions_json TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, edition_id, as_of_chapter, as_of_event_seq, config_hash)
);
CREATE INDEX IF NOT EXISTS idx_rhythm_snapshots_edition
    ON rhythm_diagnostic_snapshots(book_id, edition_id, as_of_chapter DESC);

CREATE TABLE IF NOT EXISTS chapter_segments (
    segment_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    chapter_id TEXT NOT NULL,
    effective_content_sha256 TEXT NOT NULL,
    segment_ordinal INTEGER NOT NULL,
    segment_kind TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, edition_id, chapter_id, effective_content_sha256, segment_ordinal)
);
CREATE INDEX IF NOT EXISTS idx_chapter_segments_lookup
    ON chapter_segments(book_id, edition_id, chapter_id, invalidated_at, segment_ordinal);

CREATE TABLE IF NOT EXISTS metric_observations (
    observation_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    chapter_id TEXT,
    effective_content_sha256 TEXT,
    metric_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    value_json TEXT NOT NULL,
    value_numeric REAL,
    status TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    confidence REAL,
    analyzer_version TEXT,
    config_hash TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    source_task_id TEXT,
    supersedes_observation_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    retracted_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(supersedes_observation_id) REFERENCES metric_observations(observation_id)
);
CREATE INDEX IF NOT EXISTS idx_metric_observations_active
    ON metric_observations(
        book_id, edition_id, scope_type, scope_id, metric_id, component_id, active
    );
CREATE INDEX IF NOT EXISTS idx_metric_observations_hash
    ON metric_observations(book_id, edition_id, effective_content_sha256, config_hash);

CREATE TABLE IF NOT EXISTS metric_evidence_links (
    link_id TEXT PRIMARY KEY,
    observation_id TEXT NOT NULL REFERENCES metric_observations(observation_id),
    segment_id TEXT REFERENCES chapter_segments(segment_id),
    source_span_id TEXT,
    event_id TEXT,
    contribution_kind TEXT NOT NULL,
    direction TEXT NOT NULL,
    strength REAL,
    exact_delta REAL,
    confidence REAL,
    evidence_quote TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_metric_evidence_observation
    ON metric_evidence_links(observation_id);

CREATE TABLE IF NOT EXISTS metric_runs (
    run_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    as_of_chapter INTEGER,
    as_of_event_seq INTEGER NOT NULL,
    projection_hash TEXT NOT NULL,
    effective_content_sha256 TEXT,
    registry_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    completeness REAL NOT NULL,
    confidence REAL NOT NULL,
    input_bundle_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_metric_runs_scope
    ON metric_runs(book_id, edition_id, scope_type, scope_id, created_at DESC);

CREATE TABLE IF NOT EXISTS metric_run_results (
    run_id TEXT NOT NULL REFERENCES metric_runs(run_id),
    metric_id TEXT NOT NULL,
    status TEXT NOT NULL,
    score REAL,
    lower_bound REAL,
    upper_bound REAL,
    band TEXT,
    completeness REAL NOT NULL,
    confidence REAL NOT NULL,
    components_json TEXT NOT NULL,
    missing_components_json TEXT NOT NULL,
    evidence_summary_json TEXT NOT NULL,
    threshold_interpretation TEXT NOT NULL DEFAULT '',
    recommended_action TEXT NOT NULL DEFAULT '',
    formula_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(run_id, metric_id)
);

CREATE TABLE IF NOT EXISTS workflow_handoffs (
    handoff_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    handoff_type TEXT NOT NULL,
    requested_stage TEXT NOT NULL,
    status TEXT NOT NULL,
    task_directory TEXT NOT NULL,
    prompt_path TEXT NOT NULL,
    task_manifest_path TEXT NOT NULL,
    output_schema_path TEXT NOT NULL,
    result_path TEXT NOT NULL,
    event_log_path TEXT NOT NULL,
    base_event_seq INTEGER NOT NULL,
    base_projection_hash TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL,
    metric_run_id TEXT,
    metric_bundle_hash TEXT,
    rhythm_snapshot_id TEXT,
    registry_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    claimed_by TEXT,
    claim_token TEXT,
    created_at TEXT NOT NULL,
    claimed_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    stale_at TEXT,
    error_message TEXT,
    result_json TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_workflow_handoffs_status
    ON workflow_handoffs(book_id, edition_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_handoff_events (
    event_id TEXT PRIMARY KEY,
    handoff_id TEXT NOT NULL REFERENCES workflow_handoffs(handoff_id),
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(handoff_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_workflow_handoff_events_order
    ON workflow_handoff_events(handoff_id, sequence);
"""



__all__ = ["SQL"]
