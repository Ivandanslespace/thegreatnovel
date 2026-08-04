"""Schema migration 7: independently executable SQL."""

SQL = r"""
ALTER TABLE metric_observations ADD COLUMN projection_hash TEXT;
ALTER TABLE metric_observations ADD COLUMN registry_hash TEXT;
ALTER TABLE metric_observations ADD COLUMN freshness_status TEXT NOT NULL DEFAULT 'FRESH';
ALTER TABLE metric_observations ADD COLUMN stale_reason TEXT;
ALTER TABLE metric_observations ADD COLUMN retracted_by TEXT;
ALTER TABLE metric_observations ADD COLUMN retraction_reason TEXT;

ALTER TABLE metric_runs ADD COLUMN requested_metric_ids_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE metric_runs ADD COLUMN disputed_components_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE metric_runs ADD COLUMN stale_components_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE metric_run_results ADD COLUMN disputed_components_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE metric_run_results ADD COLUMN stale_components_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE metric_run_results ADD COLUMN semantic_confidence REAL NOT NULL DEFAULT 0;
ALTER TABLE metric_run_results ADD COLUMN data_freshness TEXT NOT NULL DEFAULT 'FRESH';
ALTER TABLE metric_run_results ADD COLUMN dispute_status TEXT NOT NULL DEFAULT 'NONE';
ALTER TABLE metric_run_results ADD COLUMN formula_contribution_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE workflow_handoffs ADD COLUMN effective_content_sha256 TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN edition_status TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN result_validation_json TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN waiting_for_user_path TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN stale_reason TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN drift_detected_at TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN planning_aggregate_id TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN planning_aggregate_hash TEXT;
ALTER TABLE workflow_handoffs ADD COLUMN author_directives_hash TEXT;
ALTER TABLE candidate_plans ADD COLUMN aggregate_id TEXT;
ALTER TABLE chapter_contracts ADD COLUMN aggregate_id TEXT;

UPDATE workflow_handoffs
SET edition_status=(
    SELECT status FROM editions
    WHERE editions.book_id=workflow_handoffs.book_id
      AND editions.edition_id=workflow_handoffs.edition_id
)
WHERE edition_status IS NULL;
UPDATE workflow_handoffs
SET effective_content_sha256=(
    SELECT effective_content_sha256 FROM metric_runs
    WHERE metric_runs.run_id=workflow_handoffs.metric_run_id
)
WHERE effective_content_sha256 IS NULL AND metric_run_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS planning_aggregates (
    aggregate_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    edition_state_run_id TEXT,
    recent_chapter_run_ids_json TEXT NOT NULL DEFAULT '[]',
    window_run_ids_json TEXT NOT NULL DEFAULT '[]',
    promise_run_ids_json TEXT NOT NULL DEFAULT '[]',
    thread_run_ids_json TEXT NOT NULL DEFAULT '[]',
    metric_run_ids_json TEXT NOT NULL DEFAULT '[]',
    author_policy_json TEXT NOT NULL DEFAULT '{}',
    registry_hash TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    projection_hash TEXT NOT NULL,
    rhythm_snapshot_id TEXT,
    rhythm_snapshot_hash TEXT,
    bundle_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    stale_reason TEXT,
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_planning_aggregates_scope
    ON planning_aggregates(book_id, edition_id, created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_waiting_for_user (
    handoff_id TEXT PRIMARY KEY REFERENCES workflow_handoffs(handoff_id),
    question_id TEXT NOT NULL,
    question TEXT NOT NULL,
    reason TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '[]',
    related_artifacts_json TEXT NOT NULL DEFAULT '[]',
    required_author_decision TEXT NOT NULL,
    response_path TEXT,
    created_at TEXT NOT NULL,
    answered_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
"""



__all__ = ["SQL"]
