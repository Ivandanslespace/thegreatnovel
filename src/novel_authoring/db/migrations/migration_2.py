"""Schema migration 2: independently executable SQL."""

SQL = r"""
ALTER TABLE events ADD COLUMN information_state TEXT NOT NULL DEFAULT 'CANON';
ALTER TABLE events ADD COLUMN payload_sha256 TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN prev_event_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN event_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE events ADD COLUMN canon_commit_id TEXT;

ALTER TABLE projection_metadata ADD COLUMN state_json TEXT NOT NULL DEFAULT '{}';

CREATE TABLE IF NOT EXISTS metric_results (
    result_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    as_of_event_seq INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    score REAL NOT NULL,
    inputs_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    threshold_interpretation TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    formula_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, as_of_event_seq, metric_name, config_hash)
);

CREATE TABLE IF NOT EXISTS boundary_packets (
    packet_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    base_event_seq INTEGER NOT NULL,
    base_projection_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    packet_json TEXT NOT NULL,
    packet_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
"""



__all__ = ["SQL"]
