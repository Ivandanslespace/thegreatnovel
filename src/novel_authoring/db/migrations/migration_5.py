"""Schema migration 5: independently executable SQL."""

SQL = r"""
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



__all__ = ["SQL"]
