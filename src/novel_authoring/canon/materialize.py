from __future__ import annotations

import sqlite3
from typing import Any

from novel_authoring.contracts.draft import DraftStateChange
from novel_authoring.utils import json_dumps, utc_now


class MaterializationError(RuntimeError):
    pass


def validate_materialized_event_sources(
    connection: sqlite3.Connection, *, book_id: str, edition_id: str
) -> None:
    """Ensure every event-bearing materialized pointer resolves to events."""
    checks = (
        ("facts", "source_event_id"),
        ("knowledge_edges", "learned_event_id"),
        ("timeline_entries", "event_id"),
        ("payoff_events", "event_id"),
    )
    for table, column in checks:
        rows = connection.execute(
            f"SELECT {column} FROM {table} "
            "WHERE book_id=? AND edition_id=? AND "
            + column
            + " IS NOT NULL AND "
            + column
            + "!=''",
            (book_id, edition_id),
        ).fetchall()
        for row in rows:
            event = connection.execute(
                "SELECT 1 FROM events WHERE book_id=? AND edition_id=? AND event_id=?",
                (book_id, edition_id, str(row[0])),
            ).fetchone()
            if event is None:
                raise MaterializationError(
                    f"{table}.{column} 指向不存在的事件：{row[0]}"
                )


def _required(payload: dict[str, Any], key: str, kind: str) -> Any:
    value = payload.get(key)
    if value is None or value == "":
        raise MaterializationError(f"{kind} 状态变化缺少必填字段 {key}")
    return value


def _json(payload: dict[str, Any], key: str, default: Any) -> str:
    return json_dumps(payload.get(key, default))


def materialize_change(
    connection: sqlite3.Connection,
    *,
    book_id: str,
    change: DraftStateChange,
    source_span_id: str,
    event_id: str,
    event_seq: int,
    chapter_id: str,
    ordinal: int,
    edition_id: str = "base",
) -> None:
    """把已提交事件同步到供查询的规范化表；事件仍是唯一可重放来源。"""
    payload = change.payload
    record_id = change.record_id
    now = utc_now()
    payload_json = json_dumps(payload)
    if change.kind == "fact":
        predicate = str(_required(payload, "predicate", change.kind))
        object_value = payload.get("object", payload.get("object_json"))
        if object_value is None:
            raise MaterializationError("fact 状态变化缺少必填字段 object")
        superseded = payload.get("supersedes_fact_id")
        if superseded:
            connection.execute(
                """
                UPDATE facts SET active=0, valid_to_chapter=?, version=version+1
                WHERE book_id=? AND edition_id=? AND fact_id=?
                """,
                (chapter_id, book_id, edition_id, str(superseded)),
            )
        connection.execute(
            """
            INSERT INTO facts(
                fact_id, book_id, edition_id, subject_id, predicate, object_json, statement,
                status, source_span_id, source_event_id, confidence,
                valid_from_chapter, valid_to_chapter, supersedes_fact_id,
                active, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, ?, ?, ?, ?, 1, ?, 1)
            ON CONFLICT(book_id, edition_id, fact_id) DO UPDATE SET
                subject_id=excluded.subject_id, predicate=excluded.predicate,
                object_json=excluded.object_json, statement=excluded.statement,
                status='CANON', source_span_id=excluded.source_span_id,
                source_event_id=excluded.source_event_id,
                confidence=excluded.confidence,
                valid_from_chapter=excluded.valid_from_chapter,
                valid_to_chapter=excluded.valid_to_chapter,
                supersedes_fact_id=excluded.supersedes_fact_id,
                active=1, version=facts.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                payload.get("subject_id"),
                predicate,
                json_dumps(object_value),
                str(payload.get("statement", f"{payload.get('subject_id')}: {predicate}")),
                source_span_id,
                event_id,
                payload.get("confidence", 1.0),
                payload.get("valid_from_chapter", chapter_id),
                payload.get("valid_to_chapter"),
                payload.get("supersedes_fact_id"),
                now,
            ),
        )
    elif change.kind == "timeline":
        connection.execute(
            """
            INSERT INTO timeline_entries(
                timeline_id, book_id, edition_id, event_id, label, story_time_start,
                story_time_end, order_key, status, source_span_id,
                payload_json, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, timeline_id) DO UPDATE SET
                event_id=excluded.event_id, label=excluded.label,
                story_time_start=excluded.story_time_start,
                story_time_end=excluded.story_time_end,
                order_key=excluded.order_key, status='CANON',
                source_span_id=excluded.source_span_id,
                payload_json=excluded.payload_json,
                version=timeline_entries.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                event_id,
                str(_required(payload, "label", change.kind)),
                payload.get("story_time_start"),
                payload.get("story_time_end"),
                payload.get("order_key"),
                source_span_id,
                payload_json,
                now,
            ),
        )
    elif change.kind == "character_state":
        connection.execute(
            """
            INSERT INTO character_states(
                state_id, book_id, edition_id, character_id, as_of_event_seq, status,
                goals_json, knowledge_json, resources_json, relationships_json,
                emotion_json, plans_json, source_span_id, created_at, version
            ) VALUES (?, ?, ?, ?, ?, 'CANON', ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, state_id) DO UPDATE SET
                character_id=excluded.character_id,
                as_of_event_seq=excluded.as_of_event_seq, status='CANON',
                goals_json=excluded.goals_json,
                knowledge_json=excluded.knowledge_json,
                resources_json=excluded.resources_json,
                relationships_json=excluded.relationships_json,
                emotion_json=excluded.emotion_json, plans_json=excluded.plans_json,
                source_span_id=excluded.source_span_id,
                version=character_states.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                str(_required(payload, "character_id", change.kind)),
                event_seq,
                _json(payload, "goals", []),
                _json(payload, "knowledge", []),
                _json(payload, "resources", {}),
                _json(payload, "relationships", {}),
                _json(payload, "emotion", {}),
                _json(payload, "plans", []),
                source_span_id,
                now,
            ),
        )
    elif change.kind == "knowledge":
        connection.execute(
            """
            INSERT INTO knowledge_edges(
                edge_id, book_id, edition_id, character_id, fact_id, knowledge_state,
                learned_event_id, source_span_id, status, confidence,
                created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, 1)
            ON CONFLICT(book_id, edition_id, edge_id) DO UPDATE SET
                character_id=excluded.character_id, fact_id=excluded.fact_id,
                knowledge_state=excluded.knowledge_state,
                learned_event_id=excluded.learned_event_id,
                source_span_id=excluded.source_span_id, status='CANON',
                confidence=excluded.confidence,
                version=knowledge_edges.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                str(_required(payload, "character_id", change.kind)),
                str(_required(payload, "fact_id", change.kind)),
                str(payload.get("knowledge_state", "KNOWN")),
                event_id,
                source_span_id,
                payload.get("confidence", 1.0),
                now,
            ),
        )
    elif change.kind == "relationship":
        connection.execute(
            """
            INSERT INTO relationships(
                relationship_id, book_id, edition_id, from_entity_id, to_entity_id, status,
                trust, alignment, dependence, debt, fear, secret_exposure,
                commitment, betrayal_cost, power_delta, payload_json,
                source_span_id, created_at, version
            ) VALUES (?, ?, ?, ?, ?, 'CANON', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, relationship_id) DO UPDATE SET
                from_entity_id=excluded.from_entity_id,
                to_entity_id=excluded.to_entity_id, status='CANON',
                trust=excluded.trust, alignment=excluded.alignment,
                dependence=excluded.dependence, debt=excluded.debt,
                fear=excluded.fear, secret_exposure=excluded.secret_exposure,
                commitment=excluded.commitment,
                betrayal_cost=excluded.betrayal_cost,
                power_delta=excluded.power_delta,
                payload_json=excluded.payload_json,
                source_span_id=excluded.source_span_id,
                version=relationships.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                str(_required(payload, "from_entity_id", change.kind)),
                str(_required(payload, "to_entity_id", change.kind)),
                payload.get("trust"),
                payload.get("alignment"),
                payload.get("dependence"),
                payload.get("debt"),
                payload.get("fear"),
                payload.get("secret_exposure"),
                payload.get("commitment"),
                payload.get("betrayal_cost"),
                payload.get("power_delta"),
                payload_json,
                source_span_id,
                now,
            ),
        )
    elif change.kind == "resource":
        quantity = payload.get("after_quantity", payload.get("quantity"))
        connection.execute(
            """
            INSERT INTO resources(
                resource_id, book_id, edition_id, owner_id, resource_type, name, quantity,
                unit, status, source_span_id, payload_json, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, resource_id) DO UPDATE SET
                owner_id=excluded.owner_id, resource_type=excluded.resource_type,
                name=excluded.name, quantity=excluded.quantity, unit=excluded.unit,
                status='CANON', source_span_id=excluded.source_span_id,
                payload_json=excluded.payload_json, version=resources.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                str(_required(payload, "owner_id", change.kind)),
                str(payload.get("resource_type", "resource")),
                str(_required(payload, "name", change.kind)),
                quantity,
                payload.get("unit"),
                source_span_id,
                payload_json,
                now,
            ),
        )
    elif change.kind == "capability":
        connection.execute(
            """
            INSERT INTO capabilities(
                capability_id, book_id, edition_id, owner_id, name, absolute_capacity,
                effective_capacity, relative_standing, limits_json, status,
                source_span_id, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, 1)
            ON CONFLICT(book_id, edition_id, capability_id) DO UPDATE SET
                owner_id=excluded.owner_id, name=excluded.name,
                absolute_capacity=excluded.absolute_capacity,
                effective_capacity=excluded.effective_capacity,
                relative_standing=excluded.relative_standing,
                limits_json=excluded.limits_json, status='CANON',
                source_span_id=excluded.source_span_id,
                version=capabilities.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                str(_required(payload, "owner_id", change.kind)),
                str(_required(payload, "name", change.kind)),
                payload.get("absolute_capacity"),
                payload.get("effective_capacity"),
                payload.get("relative_standing"),
                _json(payload, "limits", {}),
                source_span_id,
                now,
            ),
        )
    elif change.kind == "thread":
        connection.execute(
            """
            INSERT INTO threads(
                thread_id, book_id, edition_id, goal, stakes, phase, introduced_chapter,
                last_advanced_chapter, target_payoff_min, target_payoff_max,
                importance, reader_visibility, progress, dependencies_json,
                status, source_span_id, payload_json, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, thread_id) DO UPDATE SET
                goal=excluded.goal, stakes=excluded.stakes, phase=excluded.phase,
                last_advanced_chapter=excluded.last_advanced_chapter,
                target_payoff_min=excluded.target_payoff_min,
                target_payoff_max=excluded.target_payoff_max,
                importance=excluded.importance,
                reader_visibility=excluded.reader_visibility,
                progress=excluded.progress,
                dependencies_json=excluded.dependencies_json, status='CANON',
                source_span_id=excluded.source_span_id,
                payload_json=excluded.payload_json, version=threads.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                str(_required(payload, "goal", change.kind)),
                str(_required(payload, "stakes", change.kind)),
                str(_required(payload, "phase", change.kind)),
                payload.get("introduced_chapter", chapter_id),
                payload.get("last_advanced_chapter", chapter_id),
                payload.get("target_payoff_min"),
                payload.get("target_payoff_max"),
                payload.get("importance", 0.5),
                payload.get("reader_visibility", 0.5),
                payload.get("progress", 0.0),
                _json(payload, "dependencies", []),
                source_span_id,
                payload_json,
                now,
            ),
        )
    elif change.kind == "promise":
        connection.execute(
            """
            INSERT INTO promises(
                promise_id, book_id, edition_id, thread_id, statement, importance,
                reader_visibility, progress, introduced_ordinal,
                last_reminded_ordinal, reminder_count, target_min_age,
                target_max_age, status, source_span_id, payload_json,
                created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, promise_id) DO UPDATE SET
                thread_id=excluded.thread_id, statement=excluded.statement,
                importance=excluded.importance,
                reader_visibility=excluded.reader_visibility,
                progress=excluded.progress,
                last_reminded_ordinal=excluded.last_reminded_ordinal,
                reminder_count=excluded.reminder_count,
                target_min_age=excluded.target_min_age,
                target_max_age=excluded.target_max_age, status='CANON',
                source_span_id=excluded.source_span_id,
                payload_json=excluded.payload_json, version=promises.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                payload.get("thread_id"),
                str(_required(payload, "statement", change.kind)),
                payload.get("importance", 0.5),
                payload.get("reader_visibility", 0.5),
                payload.get("progress", 0.0),
                payload.get("introduced_ordinal", ordinal),
                payload.get("last_reminded_ordinal"),
                payload.get("reminder_count", 0),
                payload.get("target_min_age"),
                payload.get("target_max_age", 8),
                source_span_id,
                payload_json,
                now,
            ),
        )
    elif change.kind == "payoff":
        connection.execute(
            """
            INSERT INTO payoff_events(
                payoff_id, book_id, edition_id, thread_id, payoff_type, subtype, score,
                chapter_id, event_id, status, aftershock_due_ordinal,
                payload_json, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, payoff_id) DO UPDATE SET
                thread_id=excluded.thread_id, payoff_type=excluded.payoff_type,
                subtype=excluded.subtype, score=excluded.score,
                chapter_id=excluded.chapter_id, event_id=excluded.event_id,
                status='CANON',
                aftershock_due_ordinal=excluded.aftershock_due_ordinal,
                payload_json=excluded.payload_json,
                version=payoff_events.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                payload.get("thread_id"),
                str(payload.get("payoff_type", "unspecified")),
                payload.get("subtype"),
                payload.get("score"),
                chapter_id,
                event_id,
                payload.get("aftershock_due_ordinal"),
                payload_json,
                now,
            ),
        )
    elif change.kind == "repetition":
        connection.execute(
            """
            INSERT INTO repetition_tags(
                tag_id, book_id, edition_id, chapter_id, candidate_id, event_source,
                solution_method, payoff_type, scene_topology,
                emotional_outcome, ending_type, ordinal, status,
                payload_json, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANON', ?, ?, 1)
            ON CONFLICT(book_id, edition_id, tag_id) DO UPDATE SET
                chapter_id=excluded.chapter_id, candidate_id=excluded.candidate_id,
                event_source=excluded.event_source,
                solution_method=excluded.solution_method,
                payoff_type=excluded.payoff_type,
                scene_topology=excluded.scene_topology,
                emotional_outcome=excluded.emotional_outcome,
                ending_type=excluded.ending_type, ordinal=excluded.ordinal,
                status='CANON', payload_json=excluded.payload_json,
                version=repetition_tags.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                chapter_id,
                payload.get("candidate_id"),
                payload.get("event_source"),
                payload.get("solution_method"),
                payload.get("payoff_type"),
                payload.get("scene_topology"),
                payload.get("emotional_outcome"),
                payload.get("ending_type"),
                ordinal,
                payload_json,
                now,
            ),
        )
    elif change.kind == "style":
        connection.execute(
            """
            INSERT INTO style_profiles(
                profile_id, book_id, edition_id, status, pov, tense, sentence_rhythm_json,
                dialogue_ratio, exposition_density, emotional_distance,
                voice_samples_json, forbidden_json, source_span_id,
                created_at, version
            ) VALUES (?, ?, ?, 'CANON', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(book_id, edition_id, profile_id) DO UPDATE SET
                status='CANON', pov=excluded.pov, tense=excluded.tense,
                sentence_rhythm_json=excluded.sentence_rhythm_json,
                dialogue_ratio=excluded.dialogue_ratio,
                exposition_density=excluded.exposition_density,
                emotional_distance=excluded.emotional_distance,
                voice_samples_json=excluded.voice_samples_json,
                forbidden_json=excluded.forbidden_json,
                source_span_id=excluded.source_span_id,
                version=style_profiles.version+1
            """,
            (
                record_id,
                book_id,
                edition_id,
                payload.get("pov"),
                payload.get("tense"),
                _json(payload, "sentence_rhythm", {}),
                payload.get("dialogue_ratio"),
                payload.get("exposition_density"),
                payload.get("emotional_distance"),
                _json(payload, "voice_samples", []),
                _json(payload, "forbidden", []),
                source_span_id,
                now,
            ),
        )
    else:
        raise MaterializationError(f"不支持的状态变化类型：{change.kind}")
