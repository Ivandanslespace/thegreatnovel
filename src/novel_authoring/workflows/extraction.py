from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from novel_authoring.canon.events import EventStatus, EventStore
from novel_authoring.canon.projection import rebuild_projection, validate_information_transition
from novel_authoring.contracts.extraction import (
    CapabilityExtraction,
    CharacterStateExtraction,
    EntityExtraction,
    EventExtraction,
    ExtractionBase,
    ExtractionOutput,
    FactExtraction,
    KnowledgeExtraction,
    PromiseExtraction,
    RelationshipExtraction,
    RepetitionExtraction,
    ResourceExtraction,
    StyleExtraction,
    ThreadExtraction,
    TimelineExtraction,
)
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.storage.operations import ensure_operation, find_operation
from novel_authoring.utils import json_dumps, sha256_bytes, stable_id, utc_now


class AgentContractError(RuntimeError):
    pass


def _book_workspace(database: Database, book_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise AgentContractError(f"未知 book_id：{book_id}")
    return Path(str(row["workspace_root"]))


def prepare_extraction_task(
    database: Database,
    book_id: str,
    *,
    chapter_start: int,
    chapter_end: int,
) -> dict[str, object]:
    if chapter_start < 1 or chapter_end < chapter_start:
        raise AgentContractError("章节范围无效")
    if chapter_end - chapter_start + 1 > 10:
        raise AgentContractError("单次抽取最多 10 个章块")
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT c.chapter_id, c.ordinal, c.raw_heading, c.content,
                   s.span_id, s.start_line, s.end_line, s.start_char, s.end_char
            FROM chapters c
            JOIN source_spans s ON s.chapter_id=c.chapter_id AND s.kind='chapter'
            WHERE c.book_id=? AND c.ordinal BETWEEN ? AND ?
            ORDER BY c.ordinal
            """,
            (book_id, chapter_start, chapter_end),
        ).fetchall()
    if not rows:
        raise AgentContractError("范围内没有章节")
    schema = ExtractionOutput.model_json_schema()
    schema_json = json_dumps(schema, indent=2)
    chapter_ids = [str(row["chapter_id"]) for row in rows]
    schema_hash = sha256_bytes(schema_json.encode())
    task_id = stable_id(
        "extract", book_id, ",".join(chapter_ids), schema_hash
    )
    workspace = _book_workspace(database, book_id)
    operation = ensure_operation(
        database,
        book_id,
        "base",
        task_id,
        "EXTRACTION",
        {"chapter_start": chapter_start, "chapter_end": chapter_end},
    )
    task_dir = (
        operation.input
        if operation is not None
        else workspace / "agent_tasks" / task_id
    )
    output_dir = (
        operation.output
        if operation is not None
        else workspace / "agent_outputs" / task_id
    )
    task_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_lines = [
        f"# 结构化抽取任务 `{task_id}`",
        "",
        "只依据下方原文抽取结构化信息，不补写剧情。",
        "所有记录只能标记为 INFERENCE 或 PROSE_ONLY；系统会在导入后单独 reconcile。",
        "每条记录必须引用所列 source_span_id，并提供可在原文中定位的短证据。",
        "将结果写入任务 output/ 目录的 output.json，并严格遵守 schema.json。",
        "",
    ]
    spans: list[dict[str, object]] = []
    for row in rows:
        input_lines.extend(
            [
                f"## 章块 {row['ordinal']}：{row['raw_heading']}",
                "",
                f"- chapter_id: `{row['chapter_id']}`",
                f"- source_span_id: `{row['span_id']}`",
                f"- lines: {row['start_line']}—{row['end_line']}",
                "",
                str(row["content"]),
                "",
            ]
        )
        spans.append(
            {
                "chapter_id": str(row["chapter_id"]),
                "source_span_id": str(row["span_id"]),
                "ordinal": int(row["ordinal"]),
            }
        )
    metadata = {
        "task_id": task_id,
        "task_type": "extract",
        "book_id": book_id,
        "chapter_start": chapter_start,
        "chapter_end": chapter_end,
        "source_spans": spans,
        "schema_sha256": schema_hash,
        "created_at": utc_now(),
    }
    (task_dir / "input.md").write_text("\n".join(input_lines), encoding="utf-8")
    (task_dir / "schema.json").write_text(schema_json + "\n", encoding="utf-8")
    (task_dir / "task.json").write_text(
        json_dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "task_id": task_id,
        "input": str(task_dir / "input.md"),
        "schema": str(task_dir / "schema.json"),
        "expected_output": str(output_dir / "output.json"),
        "chapters": len(rows),
    }


def _validate_sources(
    database: Database,
    task_metadata: dict[str, Any],
    output: ExtractionOutput,
) -> None:
    allowed = {
        str(item["source_span_id"])
        for item in cast(list[dict[str, Any]], task_metadata["source_spans"])
    }
    with database.connect() as connection:
        span_text = {
            str(row["span_id"]): str(row["content"])
            for row in connection.execute(
                """
                SELECT s.span_id, c.content FROM source_spans s
                JOIN chapters c ON c.chapter_id=s.chapter_id
                WHERE s.span_id IN ({})
                """.format(",".join("?" for _ in allowed)),
                tuple(sorted(allowed)),
            ).fetchall()
        }
    for record in output.records:
        if not set(record.source_span_ids) <= allowed:
            raise AgentContractError(
                f"记录 {record.local_id} 引用了任务范围外的 source span"
            )
        if not any(
            record.evidence_quote in span_text.get(span_id, "")
            for span_id in record.source_span_ids
        ):
            raise AgentContractError(
                f"记录 {record.local_id} 的 evidence_quote 无法在来源中定位"
            )


def _record_id(task_id: str, record: ExtractionBase) -> str:
    return stable_id(record.kind, task_id, record.local_id)


def _resolved(ref: str | None, id_map: dict[str, str]) -> str | None:
    if ref is None:
        return None
    return id_map.get(ref, ref)


def _insert_record(
    connection: Any,
    *,
    book_id: str,
    task_id: str,
    record: ExtractionBase,
    record_id: str,
    id_map: dict[str, str],
) -> None:
    now = utc_now()
    status = record.information_state
    source_span = record.source_span_ids[0]
    payload = record.model_dump(mode="json")
    payload_json = json_dumps(payload)
    if isinstance(record, EntityExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO entities(
                entity_id, book_id, entity_type, name, aliases_json, status,
                source_span_id, confidence, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                record.entity_type,
                record.name,
                json_dumps(record.aliases),
                status,
                source_span,
                record.confidence,
                payload_json,
                now,
            ),
        )
    elif isinstance(record, FactExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO facts(
                fact_id, book_id, subject_id, predicate, object_json, statement,
                status, source_span_id, confidence, active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.subject_ref, id_map),
                record.predicate,
                json_dumps(record.object_value),
                record.statement,
                status,
                source_span,
                record.confidence,
                now,
            ),
        )
    elif isinstance(record, TimelineExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO timeline_entries(
                timeline_id, book_id, label, story_time_start, story_time_end,
                order_key, status, source_span_id, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                record.label,
                record.story_time_start,
                record.story_time_end,
                record.order_key,
                status,
                source_span,
                payload_json,
                now,
            ),
        )
    elif isinstance(record, CharacterStateExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO character_states(
                state_id, book_id, character_id, status, goals_json, knowledge_json,
                resources_json, relationships_json, emotion_json, plans_json,
                source_span_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.character_ref, id_map),
                status,
                json_dumps(record.goals),
                json_dumps(record.knowledge),
                json_dumps(record.resources),
                json_dumps(record.relationships),
                json_dumps(record.emotion),
                json_dumps(record.plans),
                source_span,
                now,
            ),
        )
    elif isinstance(record, KnowledgeExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO knowledge_edges(
                edge_id, book_id, character_id, fact_id, knowledge_state,
                source_span_id, status, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.character_ref, id_map),
                _resolved(record.fact_ref, id_map),
                record.knowledge_state,
                source_span,
                status,
                record.confidence,
                now,
            ),
        )
    elif isinstance(record, RelationshipExtraction):
        values = record.values
        connection.execute(
            """
            INSERT OR IGNORE INTO relationships(
                relationship_id, book_id, from_entity_id, to_entity_id, status,
                trust, alignment, dependence, debt, fear, secret_exposure,
                commitment, betrayal_cost, power_delta, payload_json,
                source_span_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.from_entity_ref, id_map),
                _resolved(record.to_entity_ref, id_map),
                status,
                values.get("trust"),
                values.get("alignment"),
                values.get("dependence"),
                values.get("debt"),
                values.get("fear"),
                values.get("secret_exposure"),
                values.get("commitment"),
                values.get("betrayal_cost"),
                values.get("power_delta"),
                payload_json,
                source_span,
                now,
            ),
        )
    elif isinstance(record, ResourceExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO resources(
                resource_id, book_id, owner_id, resource_type, name, quantity,
                unit, status, source_span_id, payload_json, created_at
            ) VALUES (?, ?, ?, 'resource', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.owner_ref, id_map),
                record.name,
                record.quantity,
                record.unit,
                status,
                source_span,
                payload_json,
                now,
            ),
        )
    elif isinstance(record, CapabilityExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO capabilities(
                capability_id, book_id, owner_id, name, absolute_capacity,
                effective_capacity, relative_standing, limits_json, status,
                source_span_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.owner_ref, id_map),
                record.name,
                record.absolute_capacity,
                record.effective_capacity,
                record.relative_standing,
                json_dumps(record.limits),
                status,
                source_span,
                now,
            ),
        )
    elif isinstance(record, ThreadExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO threads(
                thread_id, book_id, goal, stakes, phase, importance,
                reader_visibility, progress, dependencies_json, status,
                source_span_id, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                record.goal,
                record.stakes,
                record.phase,
                record.importance,
                record.reader_visibility,
                record.progress,
                json_dumps(record.dependencies),
                status,
                source_span,
                payload_json,
                now,
            ),
        )
    elif isinstance(record, PromiseExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO promises(
                promise_id, book_id, thread_id, statement, importance,
                reader_visibility, progress, introduced_ordinal, target_max_age,
                status, source_span_id, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                _resolved(record.thread_ref, id_map),
                record.statement,
                record.importance,
                record.reader_visibility,
                record.progress,
                record.target_max_age,
                status,
                source_span,
                payload_json,
                now,
            ),
        )
    elif isinstance(record, StyleExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO style_profiles(
                profile_id, book_id, status, pov, tense, dialogue_ratio,
                exposition_density, emotional_distance, voice_samples_json,
                source_span_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                status,
                record.pov,
                record.tense,
                record.dialogue_ratio,
                record.exposition_density,
                record.emotional_distance,
                json_dumps([record.sample]),
                source_span,
                now,
            ),
        )
    elif isinstance(record, RepetitionExtraction):
        connection.execute(
            """
            INSERT OR IGNORE INTO repetition_tags(
                tag_id, book_id, event_source, solution_method, payoff_type,
                scene_topology, emotional_outcome, ending_type, ordinal,
                status, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                record_id,
                book_id,
                record.event_source,
                record.solution_method,
                record.payoff_type,
                record.scene_topology,
                record.emotional_outcome,
                record.ending_type,
                status,
                payload_json,
                now,
            ),
        )
    elif not isinstance(record, EventExtraction):
        raise AgentContractError(f"不支持的抽取类型：{record.kind}")

    store = EventStore(Database(Path(connection.execute("PRAGMA database_list").fetchone()[2])))
    store.append_in_transaction(
        connection,
        book_id=book_id,
        event_type=f"EXTRACTION_{record.kind.upper()}_IMPORTED",
        aggregate_type=record.kind,
        aggregate_id=record_id,
        payload=payload,
        source_kind="AGENT_OUTPUT",
        source_id=task_id,
        status=EventStatus.PENDING,
        information_state=InformationStatus(record.information_state),
    )


def import_extraction_output(
    database: Database,
    book_id: str,
    task_id: str,
    output_path: Path | None = None,
) -> dict[str, object]:
    workspace = _book_workspace(database, book_id)
    operation = find_operation(database, book_id, "base", task_id)
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else workspace / "agent_tasks" / task_id / "task.json"
    )
    if not task_path.exists():
        raise AgentContractError(f"任务不存在：{task_id}")
    metadata = json.loads(task_path.read_text(encoding="utf-8"))
    path = output_path or (
        operation.output / "output.json"
        if operation is not None
        else workspace / "agent_outputs" / task_id / "output.json"
    )
    try:
        output = ExtractionOutput.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise AgentContractError(f"output.json 不符合合同：{exc}") from exc
    if output.task_id != task_id:
        raise AgentContractError("output task_id 与任务目录不一致")
    _validate_sources(database, metadata, output)
    id_map = {
        record.local_id: _record_id(task_id, record) for record in output.records
    }
    with database.connect() as connection:
        for record in output.records:
            _insert_record(
                connection,
                book_id=book_id,
                task_id=task_id,
                record=record,
                record_id=id_map[record.local_id],
                id_map=id_map,
            )
    return {
        "task_id": task_id,
        "records_imported": len(output.records),
        "record_ids": id_map,
        "information_states": sorted({record.information_state for record in output.records}),
    }


def build_reconcile_report(database: Database, book_id: str) -> dict[str, object]:
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT fact_id, subject_id, predicate, object_json, statement,
                   status, source_span_id, confidence
            FROM facts WHERE book_id=? AND active=1
            ORDER BY subject_id, predicate, fact_id
            """,
            (book_id,),
        ).fetchall()
        pending_by_type: dict[str, list[dict[str, object]]] = {}
        record_tables = {
            "entity": ("entities", "entity_id", "source_span_id"),
            "timeline": ("timeline_entries", "timeline_id", "source_span_id"),
            "character_state": ("character_states", "state_id", "source_span_id"),
            "knowledge": ("knowledge_edges", "edge_id", "source_span_id"),
            "relationship": ("relationships", "relationship_id", "source_span_id"),
            "resource": ("resources", "resource_id", "source_span_id"),
            "capability": ("capabilities", "capability_id", "source_span_id"),
            "thread": ("threads", "thread_id", "source_span_id"),
            "promise": ("promises", "promise_id", "source_span_id"),
            "style": ("style_profiles", "profile_id", "source_span_id"),
            "repetition": ("repetition_tags", "tag_id", "NULL"),
        }
        for record_type, (table, identifier, source_column) in record_tables.items():
            record_rows = connection.execute(
                f"""
                SELECT {identifier} AS record_id, status,
                       {source_column} AS source_span_id
                FROM {table}
                WHERE book_id=? AND status IN ('INFERENCE', 'PROSE_ONLY')
                ORDER BY created_at
                """,
                (book_id,),
            ).fetchall()
            pending_by_type[record_type] = [dict(item) for item in record_rows]
        event_rows = connection.execute(
            """
            SELECT aggregate_id AS record_id, information_state AS status,
                   source_id
            FROM events source_event
            WHERE source_event.book_id=?
                  AND source_event.event_type='EXTRACTION_EVENT_IMPORTED'
                  AND source_event.information_state!='CANON'
                  AND NOT EXISTS (
                      SELECT 1 FROM events decision_event
                      WHERE decision_event.book_id=source_event.book_id
                        AND decision_event.aggregate_id=source_event.aggregate_id
                        AND decision_event.event_type IN (
                            'STORY_EVENT_CONFIRMED', 'STORY_EVENT_REJECTED'
                        )
                  )
            ORDER BY event_seq
            """,
            (book_id,),
        ).fetchall()
        pending_by_type["event"] = [dict(item) for item in event_rows]
    groups: dict[tuple[str | None, str], list[dict[str, object]]] = {}
    pending: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        key = (cast(str | None, row["subject_id"]), str(row["predicate"]))
        groups.setdefault(key, []).append(item)
        if row["status"] != InformationStatus.CANON.value:
            pending.append(item)
    pending_by_type["fact"] = pending
    conflicts = []
    for (subject_id, predicate), items in groups.items():
        objects = {str(item["object_json"]) for item in items}
        if len(objects) > 1:
            conflicts.append(
                {
                    "subject_id": subject_id,
                    "predicate": predicate,
                    "facts": items,
                }
            )
    report: dict[str, object] = {
        "book_id": book_id,
        "pending_review": pending,
        "pending_by_type": pending_by_type,
        "conflicts": conflicts,
        "generated_at": utc_now(),
    }
    workspace = _book_workspace(database, book_id)
    report_path = workspace / "reconcile_report.json"
    report_path.write_text(json_dumps(report, indent=2) + "\n", encoding="utf-8")
    report["path"] = str(report_path)
    return report


_RECONCILE_SPECS: dict[str, tuple[str, str, str, str, str]] = {
    "entity": ("entities", "entity_id", "ENTITY_CONFIRMED", "entity", "entity_id"),
    "timeline": (
        "timeline_entries",
        "timeline_id",
        "TIMELINE_ENTRY_SET",
        "timeline",
        "timeline_id",
    ),
    "character_state": (
        "character_states",
        "state_id",
        "CHARACTER_STATE_SET",
        "character_state",
        "state_id",
    ),
    "knowledge": (
        "knowledge_edges",
        "edge_id",
        "KNOWLEDGE_EDGE_SET",
        "knowledge",
        "edge_id",
    ),
    "relationship": (
        "relationships",
        "relationship_id",
        "RELATIONSHIP_SET",
        "relationship",
        "relationship_id",
    ),
    "resource": ("resources", "resource_id", "RESOURCE_SET", "resource", "resource_id"),
    "capability": (
        "capabilities",
        "capability_id",
        "CAPABILITY_SET",
        "capability",
        "capability_id",
    ),
    "thread": ("threads", "thread_id", "THREAD_SET", "thread", "thread_id"),
    "promise": ("promises", "promise_id", "PROMISE_SET", "promise", "promise_id"),
    "style": (
        "style_profiles",
        "profile_id",
        "STYLE_PROFILE_SET",
        "style",
        "profile_id",
    ),
    "repetition": (
        "repetition_tags",
        "tag_id",
        "REPETITION_TAGGED",
        "repetition",
        "tag_id",
    ),
}


def _parse_json_column(row: Any, key: str, default: object) -> object:
    value = row[key]
    return default if value in {None, ""} else json.loads(str(value))


def _canonical_record_payload(record_type: str, row: Any, record_id: str) -> dict[str, Any]:
    if record_type == "entity":
        return {
            "entity_id": record_id,
            "entity_type": row["entity_type"],
            "name": row["name"],
            "aliases": _parse_json_column(row, "aliases_json", []),
        }
    if record_type == "timeline":
        return {
            "timeline_id": record_id,
            "label": row["label"],
            "story_time_start": row["story_time_start"],
            "story_time_end": row["story_time_end"],
            "order_key": row["order_key"],
        }
    if record_type == "character_state":
        return {
            "state_id": record_id,
            "character_id": row["character_id"],
            "goals": _parse_json_column(row, "goals_json", []),
            "knowledge": _parse_json_column(row, "knowledge_json", []),
            "resources": _parse_json_column(row, "resources_json", {}),
            "relationships": _parse_json_column(row, "relationships_json", {}),
            "emotion": _parse_json_column(row, "emotion_json", {}),
            "plans": _parse_json_column(row, "plans_json", []),
        }
    if record_type == "knowledge":
        return {
            "edge_id": record_id,
            "character_id": row["character_id"],
            "fact_id": row["fact_id"],
            "knowledge_state": row["knowledge_state"],
            "confidence": row["confidence"],
        }
    if record_type == "relationship":
        payload = cast(dict[str, Any], _parse_json_column(row, "payload_json", {}))
        payload.update(
            {
                "relationship_id": record_id,
                "from_entity_id": row["from_entity_id"],
                "to_entity_id": row["to_entity_id"],
            }
        )
        return payload
    if record_type == "resource":
        return {
            "resource_id": record_id,
            "owner_id": row["owner_id"],
            "resource_type": row["resource_type"],
            "name": row["name"],
            "quantity": row["quantity"],
            "unit": row["unit"],
        }
    if record_type == "capability":
        return {
            "capability_id": record_id,
            "owner_id": row["owner_id"],
            "name": row["name"],
            "absolute_capacity": row["absolute_capacity"],
            "effective_capacity": row["effective_capacity"],
            "relative_standing": row["relative_standing"],
            "limits": _parse_json_column(row, "limits_json", {}),
        }
    if record_type == "thread":
        return {
            "thread_id": record_id,
            "goal": row["goal"],
            "stakes": row["stakes"],
            "phase": row["phase"],
            "importance": row["importance"],
            "reader_visibility": row["reader_visibility"],
            "progress": row["progress"],
            "dependencies": _parse_json_column(row, "dependencies_json", []),
        }
    if record_type == "promise":
        return {
            "promise_id": record_id,
            "thread_id": row["thread_id"],
            "statement": row["statement"],
            "importance": row["importance"],
            "reader_visibility": row["reader_visibility"],
            "progress": row["progress"],
            "introduced_ordinal": row["introduced_ordinal"],
            "target_max_age": row["target_max_age"],
        }
    if record_type == "style":
        return {
            "profile_id": record_id,
            "pov": row["pov"],
            "tense": row["tense"],
            "dialogue_ratio": row["dialogue_ratio"],
            "exposition_density": row["exposition_density"],
            "emotional_distance": row["emotional_distance"],
            "voice_samples": _parse_json_column(row, "voice_samples_json", []),
        }
    if record_type == "repetition":
        return {
            "tag_id": record_id,
            "event_source": row["event_source"],
            "solution_method": row["solution_method"],
            "payoff_type": row["payoff_type"],
            "scene_topology": row["scene_topology"],
            "emotional_outcome": row["emotional_outcome"],
            "ending_type": row["ending_type"],
        }
    raise AgentContractError(f"不支持的 record_type：{record_type}")


def reconcile_record(
    database: Database,
    book_id: str,
    record_type: str,
    record_id: str,
    *,
    decision: str,
    reason: str,
) -> dict[str, object]:
    if record_type == "fact":
        return reconcile_fact(
            database, book_id, record_id, decision=decision, reason=reason
        )
    if decision not in {"accept-source", "accept-author", "reject"}:
        raise AgentContractError("decision 必须是 accept-source、accept-author 或 reject")
    confirmation_source = (
        "AUTHOR_CONFIRMATION" if decision == "accept-author" else "SOURCE_RECONCILE"
    )
    confirmation_commit = confirmation_source
    if record_type == "event":
        with database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM events
                WHERE book_id=? AND aggregate_id=?
                      AND event_type='EXTRACTION_EVENT_IMPORTED'
                ORDER BY event_seq DESC LIMIT 1
                """,
                (book_id, record_id),
            ).fetchone()
            if row is None:
                raise AgentContractError(f"event 记录不存在：{record_id}")
            old = InformationStatus(str(row["information_state"]))
            payload = json.loads(str(row["payload_json"]))
            source_spans = payload.get("source_span_ids", [])
            source_span_id = source_spans[0] if source_spans else None
            if decision == "reject":
                event = EventStore(database).append_in_transaction(
                    connection,
                    book_id=book_id,
                    event_type="STORY_EVENT_REJECTED",
                    aggregate_type="event",
                    aggregate_id=record_id,
                    payload={"event_id": record_id, "reason": reason},
                    source_kind="RECONCILE",
                    source_id=source_span_id,
                    status=EventStatus.REJECTED,
                    information_state=old,
                )
                return {
                    "record_type": record_type,
                    "record_id": record_id,
                    "decision": decision,
                    "event_id": event.event_id,
                }
            validate_information_transition(
                old,
                InformationStatus.CANON,
                explicit_author_approval=decision == "accept-author",
                explicit_source_fact=decision == "accept-source",
            )
            if decision == "accept-source" and source_span_id is None:
                raise AgentContractError("accept-source 要求可回指 source_span")
            canonical_payload = {
                "story_event_id": record_id,
                "label": payload.get("label"),
                "payload": payload.get("payload", {}),
                "source_span_id": source_span_id,
                "reason": reason,
            }
            event = EventStore(database).append_in_transaction(
                connection,
                book_id=book_id,
                event_type="STORY_EVENT_CONFIRMED",
                aggregate_type="story_event",
                aggregate_id=record_id,
                payload=canonical_payload,
                source_kind=confirmation_source,
                source_id=source_span_id,
                status=EventStatus.COMMITTED,
                information_state=InformationStatus.CANON,
                canon_commit_id=confirmation_commit,
            )
        projection = rebuild_projection(database, book_id)
        return {
            "record_type": record_type,
            "record_id": record_id,
            "decision": decision,
            "status": "CANON",
            "event_id": event.event_id,
            "projection_sha256": projection.sha256(),
        }

    spec = _RECONCILE_SPECS.get(record_type)
    if spec is None:
        raise AgentContractError(
            f"record_type 必须是 fact、event 或 {sorted(_RECONCILE_SPECS)}"
        )
    table, identifier, event_type, aggregate_type, identifier_key = spec
    with database.connect() as connection:
        row = connection.execute(
            f"SELECT * FROM {table} WHERE book_id=? AND {identifier}=?",
            (book_id, record_id),
        ).fetchone()
        if row is None:
            raise AgentContractError(f"{record_type} 记录不存在：{record_id}")
        try:
            old = InformationStatus(str(row["status"]))
        except ValueError as exc:
            raise AgentContractError(f"记录状态不可再整理：{row['status']}") from exc
        if record_type != "repetition":
            source_span_id = row["source_span_id"]
        else:
            imported_event = connection.execute(
                """
                SELECT payload_json FROM events
                WHERE book_id=? AND aggregate_id=?
                      AND event_type=?
                ORDER BY event_seq DESC LIMIT 1
                """,
                (book_id, record_id, f"EXTRACTION_{record_type.upper()}_IMPORTED"),
            ).fetchone()
            source_span_id = None
            if imported_event is not None:
                imported_payload = json.loads(str(imported_event["payload_json"]))
                imported_spans = imported_payload.get("source_span_ids", [])
                source_span_id = imported_spans[0] if imported_spans else None
        if decision == "reject":
            connection.execute(
                f"UPDATE {table} SET status='REJECTED', version=version+1 WHERE {identifier}=?",
                (record_id,),
            )
            event = EventStore(database).append_in_transaction(
                connection,
                book_id=book_id,
                event_type=f"{event_type}_REJECTED",
                aggregate_type=aggregate_type,
                aggregate_id=record_id,
                payload={identifier_key: record_id, "reason": reason},
                source_kind="RECONCILE",
                source_id=None if source_span_id is None else str(source_span_id),
                status=EventStatus.REJECTED,
                information_state=old,
            )
            return {
                "record_type": record_type,
                "record_id": record_id,
                "decision": decision,
                "event_id": event.event_id,
            }
        validate_information_transition(
            old,
            InformationStatus.CANON,
            explicit_author_approval=decision == "accept-author",
            explicit_source_fact=decision == "accept-source",
        )
        if decision == "accept-source" and source_span_id is None:
            raise AgentContractError("accept-source 要求可回指 source_span")
        if record_type == "knowledge":
            fact = connection.execute(
                "SELECT status FROM facts WHERE book_id=? AND fact_id=?",
                (book_id, row["fact_id"]),
            ).fetchone()
            if fact is None or fact["status"] != "CANON":
                raise AgentContractError("知识边引用的 fact 必须先整理为 CANON")
        connection.execute(
            f"UPDATE {table} SET status='CANON', version=version+1 WHERE {identifier}=?",
            (record_id,),
        )
        payload = _canonical_record_payload(record_type, row, record_id)
        payload["source_span_id"] = source_span_id
        payload["reason"] = reason
        event = EventStore(database).append_in_transaction(
            connection,
            book_id=book_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=record_id,
            payload=payload,
            source_kind=confirmation_source,
            source_id=None if source_span_id is None else str(source_span_id),
            status=EventStatus.COMMITTED,
            information_state=InformationStatus.CANON,
            canon_commit_id=confirmation_commit,
        )
    projection = rebuild_projection(database, book_id)
    return {
        "record_type": record_type,
        "record_id": record_id,
        "decision": decision,
        "status": "CANON",
        "event_id": event.event_id,
        "projection_sha256": projection.sha256(),
    }


def reconcile_fact(
    database: Database,
    book_id: str,
    fact_id: str,
    *,
    decision: str,
    reason: str,
) -> dict[str, object]:
    if decision not in {"accept-source", "accept-author", "reject"}:
        raise AgentContractError("decision 必须是 accept-source、accept-author 或 reject")
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM facts WHERE book_id=? AND fact_id=?", (book_id, fact_id)
        ).fetchone()
        if row is None:
            raise AgentContractError(f"事实不存在：{fact_id}")
        old = InformationStatus(str(row["status"]))
        if decision == "reject":
            connection.execute("UPDATE facts SET active=0 WHERE fact_id=?", (fact_id,))
            EventStore(database).append_in_transaction(
                connection,
                book_id=book_id,
                event_type="FACT_REJECTED",
                aggregate_type="fact",
                aggregate_id=fact_id,
                payload={"fact_id": fact_id, "reason": reason},
                source_kind="RECONCILE",
                source_id=fact_id,
                status=EventStatus.REJECTED,
                information_state=old,
            )
            return {"fact_id": fact_id, "decision": decision, "active": False}

        validate_information_transition(
            old,
            InformationStatus.CANON,
            explicit_author_approval=decision == "accept-author",
            explicit_source_fact=decision == "accept-source",
        )
        if decision == "accept-source" and row["source_span_id"] is None:
            raise AgentContractError("accept-source 要求可回指 source_span")
        connection.execute(
            "UPDATE facts SET status='CANON', version=version+1 WHERE fact_id=?",
            (fact_id,),
        )
        payload = {
            "fact_id": fact_id,
            "subject_id": row["subject_id"],
            "predicate": row["predicate"],
            "object": json.loads(str(row["object_json"])),
            "statement": row["statement"],
            "source_span_id": row["source_span_id"],
            "reason": reason,
        }
        event = EventStore(database).append_in_transaction(
            connection,
            book_id=book_id,
            event_type="FACT_ASSERTED",
            aggregate_type="fact",
            aggregate_id=fact_id,
            payload=payload,
            source_kind="AUTHOR_CONFIRMATION"
            if decision == "accept-author"
            else "SOURCE_RECONCILE",
            source_id=str(row["source_span_id"]),
            status=EventStatus.COMMITTED,
            information_state=InformationStatus.CANON,
            canon_commit_id="AUTHOR_CONFIRMATION"
            if decision == "accept-author"
            else "SOURCE_RECONCILE",
        )
    projection = rebuild_projection(database, book_id)
    return {
        "fact_id": fact_id,
        "decision": decision,
        "status": "CANON",
        "event_id": event.event_id,
        "projection_sha256": projection.sha256(),
    }
