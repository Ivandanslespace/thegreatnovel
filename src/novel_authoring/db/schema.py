from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 8

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

MIGRATION_5_SQL = r"""
ALTER TABLE books ADD COLUMN active_edition_id TEXT;
ALTER TABLE source_documents ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE chapters ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE source_spans ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE entities ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE facts ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE events ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE timeline_entries ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE character_states ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE knowledge_edges ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE relationships ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE resources ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE capabilities ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE threads ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE promises ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE payoff_events ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE repetition_tags ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE style_profiles ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE author_directives ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE candidate_plans ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE chapter_contracts ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE drafts ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE validation_reports ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE canon_commits ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE snapshots ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE metric_results ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE boundary_packets ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';
ALTER TABLE projection_metadata ADD COLUMN edition_id TEXT NOT NULL DEFAULT 'base';

CREATE TABLE IF NOT EXISTS editions (
    edition_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    parent_edition_id TEXT REFERENCES editions(edition_id),
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    base_event_seq INTEGER NOT NULL,
    base_projection_hash TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    activated_at TEXT,
    archived_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(book_id, edition_id)
);
CREATE INDEX IF NOT EXISTS idx_editions_book_status ON editions(book_id, status);

CREATE TABLE IF NOT EXISTS edition_projection_metadata (
    book_id TEXT NOT NULL REFERENCES books(book_id),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    through_event_seq INTEGER NOT NULL DEFAULT 0,
    state_sha256 TEXT NOT NULL DEFAULT '',
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(book_id, edition_id)
);

CREATE TABLE IF NOT EXISTS edition_entity_overlays (
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    entity_id TEXT NOT NULL,
    display_name TEXT,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY(edition_id, entity_id)
);

CREATE TABLE IF NOT EXISTS revision_campaigns (
    campaign_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(book_id),
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    campaign_name TEXT NOT NULL,
    revision_kind TEXT NOT NULL,
    author_intent TEXT NOT NULL,
    target_scope_json TEXT NOT NULL,
    canon_changes_json TEXT NOT NULL DEFAULT '[]',
    entity_changes_json TEXT NOT NULL DEFAULT '[]',
    invariants_json TEXT NOT NULL DEFAULT '[]',
    must_change_json TEXT NOT NULL DEFAULT '[]',
    forbidden_changes_json TEXT NOT NULL DEFAULT '[]',
    propagation_rules_json TEXT NOT NULL DEFAULT '[]',
    style_policy_json TEXT NOT NULL DEFAULT '{}',
    completion_policy_json TEXT NOT NULL DEFAULT '{}',
    base_event_seq INTEGER NOT NULL,
    base_projection_hash TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    validated_at TEXT,
    approved_at TEXT,
    committed_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_revision_campaigns_edition
ON revision_campaigns(book_id, edition_id, status);

CREATE TABLE IF NOT EXISTS revision_impact_packets (
    packet_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL UNIQUE REFERENCES revision_campaigns(campaign_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    packet_json TEXT NOT NULL,
    packet_sha256 TEXT NOT NULL,
    deterministic_scan_completed INTEGER NOT NULL DEFAULT 0,
    codex_semantic_audit_completed INTEGER NOT NULL DEFAULT 0,
    complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS revision_impact_items (
    impact_id TEXT PRIMARY KEY,
    packet_id TEXT NOT NULL REFERENCES revision_impact_packets(packet_id),
    campaign_id TEXT NOT NULL,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    chapter_id TEXT,
    source_span_id TEXT,
    classification TEXT NOT NULL,
    severity TEXT NOT NULL,
    matched_terms_json TEXT NOT NULL DEFAULT '[]',
    details_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'OPEN',
    waiver_reason TEXT,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_revision_impact_items_campaign
ON revision_impact_items(campaign_id, classification, status);

CREATE TABLE IF NOT EXISTS revision_units (
    unit_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES revision_campaigns(campaign_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    unit_order INTEGER NOT NULL,
    base_chapter_id TEXT NOT NULL,
    base_source_span_id TEXT NOT NULL,
    base_content_sha256 TEXT NOT NULL,
    original_heading TEXT NOT NULL,
    original_content TEXT NOT NULL,
    direct_change_requirements_json TEXT NOT NULL DEFAULT '[]',
    downstream_requirements_json TEXT NOT NULL DEFAULT '[]',
    facts_to_add_json TEXT NOT NULL DEFAULT '[]',
    facts_to_supersede_json TEXT NOT NULL DEFAULT '[]',
    relationships_to_update_json TEXT NOT NULL DEFAULT '[]',
    knowledge_edges_to_update_json TEXT NOT NULL DEFAULT '[]',
    must_preserve_json TEXT NOT NULL DEFAULT '[]',
    forbidden_changes_json TEXT NOT NULL DEFAULT '[]',
    style_constraints_json TEXT NOT NULL DEFAULT '{}',
    adult_consent_constraints_json TEXT NOT NULL DEFAULT '{}',
    expected_after_state_json TEXT NOT NULL DEFAULT '{}',
    dependent_units_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'PLANNED',
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_revision_units_campaign_order
ON revision_units(campaign_id, unit_order);

CREATE TABLE IF NOT EXISTS revision_drafts (
    draft_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES revision_campaigns(campaign_id),
    unit_id TEXT NOT NULL REFERENCES revision_units(unit_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    output_json TEXT NOT NULL,
    replacement_sha256 TEXT NOT NULL,
    base_content_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    validation_run_id TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    committed_at TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_revision_drafts_campaign_status
ON revision_drafts(campaign_id, status);

CREATE TABLE IF NOT EXISTS revision_validation_reports (
    report_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    unit_id TEXT,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    validator TEXT NOT NULL,
    severity TEXT NOT NULL,
    passed INTEGER NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(run_id, validator, unit_id)
);

CREATE TABLE IF NOT EXISTS chapter_variants (
    variant_id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL REFERENCES editions(edition_id),
    campaign_id TEXT NOT NULL REFERENCES revision_campaigns(campaign_id),
    unit_id TEXT NOT NULL REFERENCES revision_units(unit_id),
    base_chapter_id TEXT NOT NULL,
    base_source_span_id TEXT NOT NULL,
    base_content_sha256 TEXT NOT NULL,
    title TEXT NOT NULL,
    replacement_content TEXT NOT NULL,
    replacement_content_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    supersedes_variant_id TEXT,
    active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    revision_commit_id TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_chapter_variant
ON chapter_variants(edition_id, base_chapter_id) WHERE active=1;

CREATE TABLE IF NOT EXISTS revision_commits (
    revision_commit_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES revision_campaigns(campaign_id),
    book_id TEXT NOT NULL,
    edition_id TEXT NOT NULL,
    unit_ids_json TEXT NOT NULL,
    variant_ids_json TEXT NOT NULL,
    event_start_seq INTEGER NOT NULL,
    event_end_seq INTEGER NOT NULL,
    author_approval TEXT NOT NULL,
    committed_at TEXT NOT NULL,
    projection_sha256 TEXT NOT NULL,
    snapshot_id TEXT,
    version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_revision_commits_campaign
ON revision_commits(campaign_id, committed_at);
"""

MIGRATION_6_SQL = r"""
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

MIGRATION_7_SQL = r"""
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

MIGRATION_8_SQL = r"""
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

MIGRATIONS: tuple[tuple[int, str], ...] = (
    (2, MIGRATION_2_SQL),
    (3, MIGRATION_3_SQL),
    (4, MIGRATION_4_SQL),
    (5, MIGRATION_5_SQL),
    (6, MIGRATION_6_SQL),
    (7, MIGRATION_7_SQL),
    (8, MIGRATION_8_SQL),
)


# Migration 5 added edition_id columns, but the original V1 tables retained
# global primary keys.  That made a materialization into one edition silently
# overwrite the row in another edition.  The integrity upgrade is deliberately
# run idempotently from Database.initialize instead of adding a migration-row
# that would break the V1 public migration contract.  Each rebuilt table uses
# a physical composite key, so edition isolation is enforced by SQLite rather
# than by generated IDs or caller discipline.
_EDITION_SCOPED_KEYS: dict[str, str | None] = {
    "facts": "fact_id",
    "timeline_entries": "timeline_id",
    "character_states": "state_id",
    "knowledge_edges": "edge_id",
    "relationships": "relationship_id",
    "resources": "resource_id",
    "capabilities": "capability_id",
    "threads": "thread_id",
    "promises": "promise_id",
    "payoff_events": "payoff_id",
    "repetition_tags": "tag_id",
    "style_profiles": "profile_id",
    "author_directives": "directive_id",
    "candidate_plans": "candidate_id",
    "chapter_contracts": "contract_id",
    "drafts": "draft_id",
    "validation_reports": "report_id",
    "canon_commits": "commit_id",
    "snapshots": "snapshot_id",
    "metric_results": "result_id",
    "boundary_packets": "packet_id",
    "projection_metadata": None,
}


def _identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _rebuild_edition_scoped_table(
    connection: sqlite3.Connection, table: str, logical_key: str | None
) -> None:
    columns = connection.execute(f"PRAGMA table_info({_identifier(table)})").fetchall()
    if not columns:
        return
    names = [str(row[1]) for row in columns]
    if "edition_id" not in names or "book_id" not in names:
        return
    pk_columns = [str(row[1]) for row in sorted(columns, key=lambda row: int(row[5])) if row[5]]
    desired = ["book_id", "edition_id"] if logical_key is None else [
        "book_id", "edition_id", logical_key
    ]
    if pk_columns == desired:
        return

    # Capture ordinary indexes before the table is replaced.  Autoindexes are
    # represented by sql=NULL and are intentionally not copied: old UNIQUE
    # constraints are precisely what caused the cross-edition overwrite.
    indexes = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table,),
    ).fetchall()
    column_defs: list[str] = []
    for row in columns:
        name = str(row[1])
        definition = f"{_identifier(name)} {str(row[2] or 'TEXT')}"
        if int(row[3]):
            definition += " NOT NULL"
        if row[4] is not None:
            definition += f" DEFAULT {row[4]}"
        column_defs.append(definition)
    column_defs.append(
        "PRIMARY KEY (" + ", ".join(_identifier(item) for item in desired) + ")"
    )
    temporary = f"__edition_scope_{table}"
    connection.execute(f"DROP TABLE IF EXISTS {_identifier(temporary)}")
    connection.execute(
        f"CREATE TABLE {_identifier(temporary)} (" + ", ".join(column_defs) + ")"
    )
    quoted_names = ", ".join(_identifier(name) for name in names)
    connection.execute(
        f"INSERT INTO {_identifier(temporary)} ({quoted_names}) "
        f"SELECT {quoted_names} FROM {_identifier(table)}"
    )
    connection.execute(f"DROP TABLE {_identifier(table)}")
    connection.execute(
        f"ALTER TABLE {_identifier(temporary)} RENAME TO {_identifier(table)}"
    )
    for index in indexes:
        sql = str(index[1])
        try:
            connection.execute(sql)
        except sqlite3.DatabaseError:
            # Stale legacy indexes must never prevent the integrity upgrade;
            # the composite primary key remains authoritative.
            continue


def _add_column_if_missing(
    connection: sqlite3.Connection, table: str, definition: str, column: str
) -> None:
    columns = {
        str(row[1]) for row in connection.execute(f"PRAGMA table_info({_identifier(table)})")
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {_identifier(table)} ADD COLUMN {definition}")


def ensure_edition_integrity_schema(connection: sqlite3.Connection) -> None:
    """Apply the idempotent Phase-A integrity/storage contract."""
    for table, logical_key in _EDITION_SCOPED_KEYS.items():
        _rebuild_edition_scoped_table(connection, table, logical_key)

    # Explicit campaign/edition anchors distinguish a parent freeze from the
    # current projection on which a campaign was opened.
    _add_column_if_missing(
        connection,
        "editions",
        "parent_base_event_seq INTEGER NOT NULL DEFAULT 0",
        "parent_base_event_seq",
    )
    _add_column_if_missing(
        connection,
        "editions",
        "parent_base_projection_hash TEXT NOT NULL DEFAULT ''",
        "parent_base_projection_hash",
    )
    _add_column_if_missing(
        connection,
        "revision_campaigns",
        "campaign_base_event_seq INTEGER NOT NULL DEFAULT 0",
        "campaign_base_event_seq",
    )
    _add_column_if_missing(
        connection,
        "revision_campaigns",
        "campaign_base_projection_hash TEXT NOT NULL DEFAULT ''",
        "campaign_base_projection_hash",
    )
    _add_column_if_missing(
        connection,
        "revision_units",
        "base_chapter_ordinal INTEGER NOT NULL DEFAULT 0",
        "base_chapter_ordinal",
    )
    _add_column_if_missing(
        connection,
        "revision_drafts",
        "parent_draft_id TEXT",
        "parent_draft_id",
    )
    _add_column_if_missing(
        connection,
        "revision_drafts",
        "revision_number INTEGER NOT NULL DEFAULT 1",
        "revision_number",
    )
    _add_column_if_missing(
        connection,
        "revision_drafts",
        "packet_sha256 TEXT NOT NULL DEFAULT ''",
        "packet_sha256",
    )
    _add_column_if_missing(
        connection,
        "revision_drafts",
        "plan_sha256 TEXT NOT NULL DEFAULT ''",
        "plan_sha256",
    )
    _add_column_if_missing(
        connection,
        "revision_drafts",
        "schema_sha256 TEXT NOT NULL DEFAULT ''",
        "schema_sha256",
    )
    _add_column_if_missing(
        connection,
        "chapter_variants",
        "committed_event_seq INTEGER",
        "committed_event_seq",
    )
    _add_column_if_missing(
        connection,
        "source_spans",
        "variant_id TEXT",
        "variant_id",
    )
    _add_column_if_missing(
        connection,
        "source_spans",
        "revision_commit_id TEXT",
        "revision_commit_id",
    )
    _add_column_if_missing(
        connection,
        "source_spans",
        "payload_json TEXT NOT NULL DEFAULT '{}'",
        "payload_json",
    )
    _add_column_if_missing(
        connection,
        "revision_impact_packets",
        "audit_task_id TEXT NOT NULL DEFAULT ''",
        "audit_task_id",
    )
    _add_column_if_missing(
        connection,
        "revision_impact_packets",
        "audit_schema_sha256 TEXT NOT NULL DEFAULT ''",
        "audit_schema_sha256",
    )
    _add_column_if_missing(
        connection,
        "revision_impact_packets",
        "analyzer_versions_json TEXT NOT NULL DEFAULT '{}'",
        "analyzer_versions_json",
    )

    # The legacy chapter_fts table is immutable/base-only.  A separate FTS5
    # index keeps variant正文 edition-scoped without deleting or replacing the
    # source index used by base edition queries.
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS edition_chapter_fts USING fts5(
            edition_id UNINDEXED,
            chapter_id UNINDEXED,
            variant_id UNINDEXED,
            heading,
            content,
            tokenize='trigram'
        )
        """
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_metric_results_edition "
        "ON metric_results(book_id, edition_id, as_of_event_seq, metric_name, config_hash)"
    )


def ensure_rhythm_schema(connection: sqlite3.Connection) -> None:
    """Upgrade legacy promise columns only.

    New storage for this release is declared in ``MIGRATION_6_SQL``.  This
    helper remains solely for databases created by the earlier rhythm patch,
    and deliberately does not create any new tables during initialization.
    """
    additions = (
        ("title_raw TEXT NOT NULL DEFAULT ''", "title_raw"),
        ("last_advanced_ordinal INTEGER", "last_advanced_ordinal"),
        ("dormancy_target INTEGER NOT NULL DEFAULT 8", "dormancy_target"),
        ("resolution_readiness REAL NOT NULL DEFAULT 0", "resolution_readiness"),
        ("dependencies_ready INTEGER NOT NULL DEFAULT 0", "dependencies_ready"),
        ("promise_horizon TEXT NOT NULL DEFAULT 'medium'", "promise_horizon"),
        ("author_deferred_until INTEGER", "author_deferred_until"),
    )
    for definition, column in additions:
        _add_column_if_missing(connection, "promises", definition, column)


def ensure_workbench_schema(connection: sqlite3.Connection) -> None:
    """Keep the Phase-G/J handoff additions compatible with early v7 DBs.

    Migration 7 is intentionally recorded once.  During development, a v7
    database could therefore exist before the final handoff directive hash
    column was added to that migration.  This small additive check lets those
    databases initialize safely without rewriting migration history.
    """
    _add_column_if_missing(
        connection,
        "workflow_handoffs",
        "author_directives_hash TEXT",
        "author_directives_hash",
    )


def ensure_atlas_schema(connection: sqlite3.Connection) -> None:
    """Keep early Migration-8 databases compatible without rewriting history."""
    additions = (
        ("parent_atlas_id TEXT", "parent_atlas_id"),
        ("effective_content_sha256 TEXT NOT NULL DEFAULT ''", "effective_content_sha256"),
        ("registry_hash TEXT NOT NULL DEFAULT ''", "registry_hash"),
        ("config_hash TEXT NOT NULL DEFAULT ''", "config_hash"),
        ("analyzer_versions_hash TEXT NOT NULL DEFAULT ''", "analyzer_versions_hash"),
        ("horizon_id TEXT", "horizon_id"),
        ("horizon_hash TEXT NOT NULL DEFAULT ''", "horizon_hash"),
        ("atlas_content_hash TEXT NOT NULL DEFAULT ''", "atlas_content_hash"),
        ("accepted_by TEXT", "accepted_by"),
        ("accepted_at TEXT", "accepted_at"),
    )
    for definition, column in additions:
        _add_column_if_missing(connection, "story_atlases", definition, column)
    for definition, column in (
        ("atlas_version INTEGER NOT NULL DEFAULT 1", "atlas_version"),
        ("atlas_hash TEXT NOT NULL DEFAULT ''", "atlas_hash"),
    ):
        _add_column_if_missing(connection, "story_atlas_usage", definition, column)
    for definition, column in (
        ("atlas_version INTEGER", "atlas_version"),
        ("atlas_hash TEXT NOT NULL DEFAULT ''", "atlas_hash"),
        ("horizon_hash TEXT NOT NULL DEFAULT ''", "horizon_hash"),
        ("source_manifest_sha256 TEXT NOT NULL DEFAULT ''", "source_manifest_sha256"),
        (
            "input_effective_content_sha256 TEXT NOT NULL DEFAULT ''",
            "input_effective_content_sha256",
        ),
        ("registry_hash TEXT NOT NULL DEFAULT ''", "registry_hash"),
        ("config_hash TEXT NOT NULL DEFAULT ''", "config_hash"),
        ("author_directives_hash TEXT NOT NULL DEFAULT ''", "author_directives_hash"),
        ("metric_bundle_hash TEXT NOT NULL DEFAULT ''", "metric_bundle_hash"),
    ):
        _add_column_if_missing(connection, "batch_working_projections", definition, column)
    for definition, column in (
        ("atlas_hash TEXT NOT NULL DEFAULT ''", "atlas_hash"),
        ("horizon_hash TEXT NOT NULL DEFAULT ''", "horizon_hash"),
    ):
        _add_column_if_missing(connection, "batch_checkpoints", definition, column)
    for definition, column in (
        ("provisional_state_hash TEXT NOT NULL DEFAULT ''", "provisional_state_hash"),
        ("boundary_hash TEXT NOT NULL DEFAULT ''", "boundary_hash"),
        ("contract_ids_json TEXT NOT NULL DEFAULT '[]'", "contract_ids_json"),
        ("validation_report_ids_json TEXT NOT NULL DEFAULT '[]'", "validation_report_ids_json"),
        ("failure_reason TEXT", "failure_reason"),
    ):
        _add_column_if_missing(connection, "batch_chunk_states", definition, column)
    for definition, column in (
        ("atlas_id TEXT", "atlas_id"),
        ("atlas_version INTEGER", "atlas_version"),
        ("atlas_manifest_hash TEXT", "atlas_manifest_hash"),
        ("horizon_hash TEXT", "horizon_hash"),
        ("batch_id TEXT", "batch_id"),
        ("batch_plan_hash TEXT", "batch_plan_hash"),
        ("readiness_status TEXT", "readiness_status"),
    ):
        _add_column_if_missing(connection, "workflow_handoffs", definition, column)
    for definition, column in (
        ("atlas_id TEXT", "atlas_id"),
        ("atlas_version INTEGER", "atlas_version"),
        ("atlas_manifest_hash TEXT", "atlas_manifest_hash"),
        ("horizon_hash TEXT", "horizon_hash"),
    ):
        _add_column_if_missing(connection, "planning_aggregates", definition, column)
