from __future__ import annotations

SCHEMA_VERSION = 4

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS books (
    book_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode TEXT NOT NULL,
    source_root TEXT NOT NULL,
    workspace_root TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS source_documents (
    document_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    encoding TEXT NOT NULL,
    byte_size INTEGER NOT NULL,
    line_count INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    order_confidence REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'CANON',
    imported_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, relative_path),
    UNIQUE(book_id, sha256)
);

CREATE TABLE IF NOT EXISTS chapters (
    chapter_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    document_id TEXT NOT NULL REFERENCES source_documents(document_id),
    ordinal INTEGER NOT NULL,
    raw_heading TEXT NOT NULL,
    chapter_number_text TEXT,
    title TEXT NOT NULL,
    volume_title TEXT,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    summary TEXT,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(document_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_chapters_book_ordinal ON chapters(book_id, ordinal);

CREATE TABLE IF NOT EXISTS source_spans (
    span_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    document_id TEXT NOT NULL REFERENCES source_documents(document_id),
    chapter_id TEXT REFERENCES chapters(chapter_id),
    kind TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    text_sha256 TEXT NOT NULL,
    excerpt TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_source_spans_chapter ON source_spans(chapter_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chapter_fts USING fts5(
    chapter_id UNINDEXED,
    book_id UNINDEXED,
    heading,
    content,
    tokenize='trigram'
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, entity_type TEXT NOT NULL,
    name TEXT NOT NULL, aliases_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL,
    source_span_id TEXT, confidence REAL, payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_entities_book_name ON entities(book_id, name);

CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, subject_id TEXT, predicate TEXT NOT NULL,
    object_json TEXT NOT NULL, statement TEXT NOT NULL, status TEXT NOT NULL,
    source_span_id TEXT, source_event_id TEXT, confidence REAL, valid_from_chapter TEXT,
    valid_to_chapter TEXT, supersedes_fact_id TEXT, active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_facts_book_status ON facts(book_id, status, active);

CREATE TABLE IF NOT EXISTS events (
    event_seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
    book_id TEXT NOT NULL, event_type TEXT NOT NULL, aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL, payload_json TEXT NOT NULL, source_kind TEXT NOT NULL,
    source_id TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_events_book_seq ON events(book_id, event_seq);

CREATE TABLE IF NOT EXISTS timeline_entries (
    timeline_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, event_id TEXT, label TEXT NOT NULL,
    story_time_start TEXT, story_time_end TEXT, order_key REAL, status TEXT NOT NULL,
    source_span_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS character_states (
    state_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, character_id TEXT NOT NULL,
    as_of_event_seq INTEGER, status TEXT NOT NULL, goals_json TEXT NOT NULL DEFAULT '[]',
    knowledge_json TEXT NOT NULL DEFAULT '[]', resources_json TEXT NOT NULL DEFAULT '{}',
    relationships_json TEXT NOT NULL DEFAULT '{}', emotion_json TEXT NOT NULL DEFAULT '{}',
    plans_json TEXT NOT NULL DEFAULT '[]', source_span_id TEXT, created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    edge_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, character_id TEXT NOT NULL,
    fact_id TEXT NOT NULL, knowledge_state TEXT NOT NULL, learned_event_id TEXT,
    source_span_id TEXT, status TEXT NOT NULL, confidence REAL, created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS relationships (
    relationship_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, from_entity_id TEXT NOT NULL,
    to_entity_id TEXT NOT NULL, status TEXT NOT NULL, trust REAL, alignment REAL,
    dependence REAL, debt REAL, fear REAL, secret_exposure REAL, commitment REAL,
    betrayal_cost REAL, power_delta REAL, payload_json TEXT NOT NULL DEFAULT '{}',
    source_span_id TEXT, created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS resources (
    resource_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, owner_id TEXT NOT NULL,
    resource_type TEXT NOT NULL, name TEXT NOT NULL, quantity REAL, unit TEXT,
    status TEXT NOT NULL, source_span_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS capabilities (
    capability_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, owner_id TEXT NOT NULL,
    name TEXT NOT NULL, absolute_capacity REAL, effective_capacity REAL,
    relative_standing REAL, limits_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL,
    source_span_id TEXT, created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, goal TEXT NOT NULL, stakes TEXT NOT NULL,
    phase TEXT NOT NULL, introduced_chapter TEXT, last_advanced_chapter TEXT,
    target_payoff_min INTEGER, target_payoff_max INTEGER, importance REAL NOT NULL,
    reader_visibility REAL NOT NULL, progress REAL NOT NULL,
    dependencies_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL, source_span_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_threads_book_status ON threads(book_id, status);

CREATE TABLE IF NOT EXISTS promises (
    promise_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, thread_id TEXT, statement TEXT NOT NULL,
    importance REAL NOT NULL, reader_visibility REAL NOT NULL, progress REAL NOT NULL,
    introduced_ordinal INTEGER NOT NULL, last_reminded_ordinal INTEGER,
    reminder_count INTEGER NOT NULL DEFAULT 0,
    target_min_age INTEGER, target_max_age INTEGER NOT NULL, status TEXT NOT NULL,
    source_span_id TEXT, payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payoff_events (
    payoff_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, thread_id TEXT, payoff_type TEXT NOT NULL,
    subtype TEXT, score REAL, chapter_id TEXT, event_id TEXT, status TEXT NOT NULL,
    aftershock_due_ordinal INTEGER, payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS repetition_tags (
    tag_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, chapter_id TEXT, candidate_id TEXT,
    event_source TEXT, solution_method TEXT, payoff_type TEXT, scene_topology TEXT,
    emotional_outcome TEXT, ending_type TEXT, ordinal INTEGER NOT NULL, status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS style_profiles (
    profile_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, status TEXT NOT NULL,
    pov TEXT, tense TEXT, sentence_rhythm_json TEXT NOT NULL DEFAULT '{}', dialogue_ratio REAL,
    exposition_density TEXT, emotional_distance TEXT, voice_samples_json TEXT NOT NULL DEFAULT '[]',
    forbidden_json TEXT NOT NULL DEFAULT '[]', source_span_id TEXT, created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS author_directives (
    directive_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, directive_type TEXT NOT NULL,
    content TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    source TEXT NOT NULL, created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS candidate_plans (
    candidate_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, task_id TEXT, rank INTEGER,
    primary_thread_id TEXT, primary_function TEXT NOT NULL,
    secondary_functions_json TEXT NOT NULL DEFAULT '[]',
    plan_json TEXT NOT NULL, score_json TEXT NOT NULL, gate_report_json TEXT NOT NULL,
    selection_status TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS chapter_contracts (
    contract_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, candidate_id TEXT,
    target_chapter_ordinal INTEGER NOT NULL, mode TEXT NOT NULL, contract_json TEXT NOT NULL,
    contract_sha256 TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS drafts (
    draft_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, contract_id TEXT NOT NULL,
    candidate_id TEXT, file_path TEXT NOT NULL, content_sha256 TEXT NOT NULL,
    status TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
    approved_at TEXT, committed_at TEXT, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS validation_reports (
    report_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, draft_id TEXT NOT NULL,
    validator TEXT NOT NULL, severity TEXT NOT NULL, passed INTEGER NOT NULL,
    report_json TEXT NOT NULL, created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_validation_draft ON validation_reports(draft_id, passed);

CREATE TABLE IF NOT EXISTS canon_commits (
    commit_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, draft_id TEXT NOT NULL UNIQUE,
    event_start_seq INTEGER, event_end_seq INTEGER, chapter_id TEXT NOT NULL,
    author_approval TEXT NOT NULL, committed_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY, book_id TEXT NOT NULL, through_event_seq INTEGER NOT NULL,
    state_sha256 TEXT NOT NULL, state_json TEXT NOT NULL, file_path TEXT,
    created_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS projection_metadata (
    book_id TEXT PRIMARY KEY, through_event_seq INTEGER NOT NULL DEFAULT 0,
    state_sha256 TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
);
"""

MIGRATION_2_SQL = r"""
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

MIGRATION_3_SQL = r"""
ALTER TABLE drafts ADD COLUMN task_id TEXT;
ALTER TABLE drafts ADD COLUMN chapter_title TEXT NOT NULL DEFAULT '';
ALTER TABLE drafts ADD COLUMN output_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE drafts ADD COLUMN base_event_seq INTEGER NOT NULL DEFAULT 0;
ALTER TABLE drafts ADD COLUMN base_projection_hash TEXT NOT NULL DEFAULT '';
"""

MIGRATION_4_SQL = r"""
ALTER TABLE drafts ADD COLUMN validation_run_id TEXT;
ALTER TABLE validation_reports ADD COLUMN run_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_validation_run
ON validation_reports(draft_id, run_id, validator);
"""

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (2, MIGRATION_2_SQL),
    (3, MIGRATION_3_SQL),
    (4, MIGRATION_4_SQL),
)
