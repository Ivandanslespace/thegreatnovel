from __future__ import annotations

from pathlib import Path
from typing import Any

from novel_authoring.canon.materialize import materialize_change
from novel_authoring.contracts.draft import DraftStateChange
from novel_authoring.db.database import Database


def test_every_approved_state_kind_materializes(tmp_path: Path) -> None:
    database = Database(tmp_path / "state.sqlite3")
    database.initialize()
    payloads: list[tuple[str, str, dict[str, Any]]] = [
        (
            "fact",
            "fact_1",
            {"subject_id": "hero", "predicate": "door", "object": "open"},
        ),
        ("timeline", "timeline_1", {"label": "天亮", "order_key": 2}),
        ("character_state", "state_1", {"character_id": "hero"}),
        (
            "knowledge",
            "knowledge_1",
            {"character_id": "hero", "fact_id": "fact_1"},
        ),
        (
            "relationship",
            "relationship_1",
            {"from_entity_id": "hero", "to_entity_id": "ally", "trust": 0.5},
        ),
        (
            "resource",
            "resource_1",
            {"owner_id": "hero", "name": "木料", "after_quantity": 3},
        ),
        (
            "capability",
            "capability_1",
            {"owner_id": "hero", "name": "修理", "absolute_capacity": 80},
        ),
        (
            "thread",
            "thread_1",
            {"goal": "守门", "stakes": "失去据点", "phase": "active"},
        ),
        ("promise", "promise_1", {"statement": "三章内回答无线电"}),
        ("payoff", "payoff_1", {"payoff_type": "partial"}),
        ("repetition", "tag_1", {"event_source": "夜袭"}),
        (
            "style",
            "style_1",
            {"pov": "第三人称限知", "voice_samples": ["他没有回头。"]},
        ),
    ]
    tables = (
        "facts",
        "timeline_entries",
        "character_states",
        "knowledge_edges",
        "relationships",
        "resources",
        "capabilities",
        "threads",
        "promises",
        "payoff_events",
        "repetition_tags",
        "style_profiles",
    )
    with database.connect() as connection:
        for index, (kind, record_id, payload) in enumerate(payloads, 1):
            materialize_change(
                connection,
                book_id="materialize-book",
                change=DraftStateChange(
                    kind=kind,  # type: ignore[arg-type]
                    record_id=record_id,
                    payload=payload,
                    evidence_quotes=["合成证据"],
                ),
                source_span_id="span_1",
                event_id=f"event_{index}",
                event_seq=index,
                chapter_id="chapter_1",
                ordinal=1,
            )
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in tables
        }
    assert counts == dict.fromkeys(tables, 1)
