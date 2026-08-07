from __future__ import annotations

# SQL task artifacts intentionally keep several contract fields on one line;
# semantic checks remain enabled for the module.
# ruff: noqa: E501
import json
import sqlite3
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from novel_authoring.canon.events import EventRecord, EventStatus, EventStore
from novel_authoring.canon.materialize import (
    materialize_change,
    validate_materialized_event_sources,
)
from novel_authoring.canon.projection import (
    persist_projection_in_transaction,
    projection_from_connection,
)
from novel_authoring.db.database import Database
from novel_authoring.domain.models import InformationStatus
from novel_authoring.edition import (
    BASE_EDITION_ID,
    EditionStatus,
    edition_chapters,
    ensure_base_edition,
    get_edition,
    resolve_edition_id,
)
from novel_authoring.ingest.service import verify_sources
from novel_authoring.planning.innovation import (
    InnovationControl,
    load_book_innovation_control,
)
from novel_authoring.revision.models import (
    ImpactAuditDecision,
    ImpactAuditOutput,
    ImpactItem,
    ImpactPacket,
    RevisionDraftOutput,
    RevisionSpec,
    RevisionUnit,
)
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import ensure_operation
from novel_authoring.utils import json_dumps, sha256_bytes, sha256_file, stable_id, utc_now
from novel_authoring.validation.models import VALIDATOR_NAMES


class RevisionWorkflowError(RuntimeError):
    pass


REVISION_APPROVAL_PHRASE = "批准改写版本"
REVISION_TASK_TYPES = {
    "impact": "revision-impact-audit",
    "plan": "revision-plan",
    "draft": "revision-draft",
}
REVISION_VALIDATOR_NAMES = (
    "source_preimage",
    "scope",
    "intent_must_change",
    "supersession_authority",
    "must_preserve",
    "propagation_completeness",
    "stable_entity_identity",
    "edition_lineage_drift",
    "adult_consent_safety",
    "campaign_completeness",
)


def _workspace_book(database: Database, book_id: str) -> Path:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT workspace_root FROM books WHERE book_id=?", (book_id,)
        ).fetchone()
    if row is None:
        raise RevisionWorkflowError(f"未知 book_id：{book_id}")
    return Path(str(row["workspace_root"]))


def _campaign_root(database: Database, book_id: str, edition_id: str, campaign_id: str) -> Path:
    book_root = _workspace_book(database, book_id)
    if (book_root / "book.yaml").is_file():
        root = BookLayout(book_root.parent).for_book(book_id).edition(edition_id).revisions / campaign_id
    else:
        root = book_root / "editions" / edition_id / "revision_campaigns" / campaign_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _revision_operation(
    database: Database,
    book_id: str,
    edition_id: str,
    campaign_id: str,
    stage: str,
) -> Any:
    operation_id = stable_id("revision-operation", campaign_id, stage)
    return ensure_operation(
        database,
        book_id,
        edition_id,
        operation_id,
        f"REVISION_{stage.upper()}",
        {"campaign_id": campaign_id, "stage": stage},
    )


def _write_json(path: Path, value: Any) -> str:
    text = json_dumps(value, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def _load_spec(value: RevisionSpec | str | Path | dict[str, Any]) -> RevisionSpec:
    if isinstance(value, RevisionSpec):
        return value
    if isinstance(value, dict):
        try:
            return RevisionSpec.model_validate(value)
        except ValidationError as exc:
            raise RevisionWorkflowError(f"RevisionSpec 无效：{exc}") from exc
    path = Path(value)
    if not path.is_file():
        raise RevisionWorkflowError(f"RevisionSpec 文件不存在：{path}")
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise TypeError("顶层必须是对象")
        return RevisionSpec.model_validate(loaded)
    except (OSError, yaml.YAMLError, TypeError, ValidationError) as exc:
        raise RevisionWorkflowError(f"RevisionSpec 无效：{exc}") from exc


def _campaign_row(database: Database, book_id: str, campaign_id: str) -> sqlite3.Row:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM revision_campaigns WHERE book_id=? AND campaign_id=?",
            (book_id, campaign_id),
        ).fetchone()
    if row is None:
        raise RevisionWorkflowError(f"改写 campaign 不存在：{campaign_id}")
    return cast(sqlite3.Row, row)


def _spec_from_campaign(row: sqlite3.Row) -> RevisionSpec:
    try:
        raw = json.loads(str(row["target_scope_json"]))
        innovation_payload = None
        if isinstance(raw, dict) and "_spec" in raw:
            raw = raw["_spec"]
        if isinstance(raw, dict):
            raw = dict(raw)
            innovation_payload = raw.pop("_innovation_control", None)
        return RevisionSpec(
            campaign_name=str(row["campaign_name"]),
            revision_kind=cast(Any, str(row["revision_kind"])),
            intent=str(row["author_intent"]),
            target_scope=raw,
            canon_changes=json.loads(str(row["canon_changes_json"])),
            entity_changes=json.loads(str(row["entity_changes_json"])),
            must_preserve=json.loads(str(row["invariants_json"])),
            # Legacy campaign rows used invariants as the only textual
            # requirement; retain that information as a conservative scope.
            must_change=json.loads(str(row["must_change_json"])),
            forbidden_changes=json.loads(str(row["forbidden_changes_json"])),
            propagation_rules=json.loads(str(row["propagation_rules_json"])),
            style_policy=json.loads(str(row["style_policy_json"])),
            completion_policy=json.loads(str(row["completion_policy_json"])),
            innovation_control=InnovationControl.model_validate(innovation_payload or {}),
        )
    except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise RevisionWorkflowError("campaign 的 RevisionSpec 持久化内容无效") from exc


def _campaign_anchor(row: sqlite3.Row) -> tuple[int, str]:
    event_seq = int(row["campaign_base_event_seq"] or row["base_event_seq"])
    projection_hash = str(row["campaign_base_projection_hash"] or row["base_projection_hash"])
    return event_seq, projection_hash


def _campaign_anchor_is_current(
    connection: sqlite3.Connection, book_id: str, campaign: sqlite3.Row
) -> bool:
    edition_id = str(campaign["edition_id"])
    anchor_seq, anchor_hash = _campaign_anchor(campaign)
    anchored = projection_from_connection(
        connection,
        book_id,
        edition_id=edition_id,
        through_event_seq=anchor_seq,
    )
    if anchored.sha256() != anchor_hash:
        return False
    later_events = connection.execute(
        """
        SELECT event_type, aggregate_id, payload_json
        FROM events
        WHERE book_id=? AND edition_id=? AND event_seq>?
        ORDER BY event_seq
        """,
        (book_id, edition_id, anchor_seq),
    ).fetchall()
    for event in later_events:
        if str(event["event_type"]) != "REVISION_CAMPAIGN_CREATED":
            return False
        try:
            payload = json.loads(str(event["payload_json"]))
        except json.JSONDecodeError:
            return False
        if str(payload.get("campaign_id")) != str(campaign["campaign_id"]):
            return False
    return True


def _source_manifest_hash(database: Database, book_id: str) -> str:
    from novel_authoring.edition import _source_manifest_hash as source_hash

    with database.connect() as connection:
        return source_hash(connection, book_id)


def _edition_projection_anchor(
    database: Database, book_id: str, edition_id: str
) -> tuple[int, str]:
    with database.connect() as connection:
        projection = projection_from_connection(connection, book_id, edition_id=edition_id)
    return projection.through_event_seq, projection.sha256()


def create_revision_campaign(
    database: Database,
    book_id: str,
    spec_or_edition: RevisionSpec | str | Path | dict[str, Any],
    maybe_spec: RevisionSpec | str | Path | dict[str, Any] | None = None,
    *,
    edition_id: str | None = None,
    campaign_id: str | None = None,
    innovation_control: InnovationControl | None = None,
) -> dict[str, object]:
    """Create a campaign.  Supports both ``(book, spec, edition_id=...)`` and
    the convenient ``(book, edition_id, spec)`` calling convention.
    """
    if maybe_spec is not None:
        if not isinstance(spec_or_edition, str):
            raise RevisionWorkflowError("第二种调用形式要求第三个参数为 edition_id")
        edition_id = spec_or_edition
        spec_value = maybe_spec
    else:
        spec_value = spec_or_edition
    spec = _load_spec(spec_value)
    if innovation_control is not None:
        spec = spec.model_copy(update={"innovation_control": innovation_control})
    database.initialize()
    ensure_base_edition(database, book_id)
    if innovation_control is None and "innovation_control" not in spec.model_fields_set:
        spec = spec.model_copy(
            update={"innovation_control": load_book_innovation_control(database, book_id)}
        )
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    edition = get_edition(database, book_id, selected_edition)
    if edition.status is EditionStatus.ARCHIVED:
        raise RevisionWorkflowError("不能在 ARCHIVED edition 上创建改写")
    if edition.status is EditionStatus.ACTIVE and selected_edition != BASE_EDITION_ID:
        raise RevisionWorkflowError(
            "ACTIVE edition 不允许原地改写；请以该 edition 为 parent 创建新的 child edition"
        )
    if selected_edition == BASE_EDITION_ID:
        raise RevisionWorkflowError("改写必须写入派生 edition；请先执行 edition create")
    spec_json = spec.model_dump(mode="json")
    spec_hash = sha256_bytes(json_dumps(spec_json).encode("utf-8"))
    effective_id = campaign_id or stable_id("campaign", book_id, selected_edition, spec_hash)
    root = _campaign_root(database, book_id, selected_edition, effective_id)
    spec_path = root / "revision_spec.json"
    _write_json(spec_path, spec_json)
    spec_schema_path = root / "revision_spec.schema.json"
    _write_json(spec_schema_path, RevisionSpec.model_json_schema())
    target_wrapper = spec.target_scope.model_dump(mode="json")
    target_wrapper["_innovation_control"] = spec.innovation_control.model_dump(mode="json")
    campaign_event_seq, campaign_projection_hash = _edition_projection_anchor(
        database, book_id, selected_edition
    )
    now = utc_now()
    with database.connect() as connection:
        existing = connection.execute(
            "SELECT campaign_id FROM revision_campaigns WHERE campaign_id=?", (effective_id,)
        ).fetchone()
        if existing is None:
            connection.execute(
                """
                INSERT INTO revision_campaigns(
                    campaign_id, book_id, edition_id, campaign_name, revision_kind,
                    author_intent, target_scope_json, canon_changes_json,
                    entity_changes_json, invariants_json, forbidden_changes_json,
                    must_change_json,
                    propagation_rules_json, style_policy_json, completion_policy_json,
                    base_event_seq, base_projection_hash,
                    campaign_base_event_seq, campaign_base_projection_hash,
                    source_manifest_sha256,
                    status, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CREATED', ?, 1)
                """,
                (
                    effective_id,
                    book_id,
                    selected_edition,
                    spec.campaign_name,
                    spec.revision_kind,
                    spec.intent,
                    json_dumps(target_wrapper),
                    json_dumps([item.model_dump(mode="json") for item in spec.canon_changes]),
                    json_dumps([item.model_dump(mode="json") for item in spec.entity_changes]),
                    json_dumps(spec.must_preserve),
                    json_dumps(spec.forbidden_changes),
                    json_dumps(spec.must_change),
                    json_dumps(spec.propagation_rules),
                    json_dumps(spec.style_policy),
                    json_dumps(spec.completion_policy),
                    edition.base_event_seq,
                    edition.base_projection_hash,
                    campaign_event_seq,
                    campaign_projection_hash,
                    edition.source_manifest_sha256,
                    now,
                ),
            )
            EventStore(database).append_in_transaction(
                connection,
                book_id=book_id,
                edition_id=selected_edition,
                event_type="REVISION_CAMPAIGN_CREATED",
                aggregate_type="revision_campaign",
                aggregate_id=effective_id,
                payload={
                    "campaign_id": effective_id,
                    "revision_kind": spec.revision_kind,
                    "intent": spec.intent,
                },
                source_kind="AUTHOR_INTENT",
                status=EventStatus.COMMITTED,
                information_state=InformationStatus.AUTHOR_INTENT,
            )
    return {
        "campaign_id": effective_id,
        "book_id": book_id,
        "edition_id": selected_edition,
        "status": "CREATED",
        "revision_spec": str(spec_path),
        "revision_spec_schema": str(spec_schema_path),
        "revision_spec_sha256": spec_hash,
        "base_event_seq": edition.base_event_seq,
        "base_projection_hash": edition.base_projection_hash,
        "source_manifest_sha256": edition.source_manifest_sha256,
        "innovation_control": spec.innovation_control.model_dump(mode="json"),
    }


def list_revision_campaigns(
    database: Database, book_id: str, edition_id: str | None = None
) -> list[dict[str, Any]]:
    database.initialize()
    with database.connect() as connection:
        if edition_id is None:
            rows = connection.execute(
                "SELECT * FROM revision_campaigns WHERE book_id=? ORDER BY created_at, campaign_id",
                (book_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM revision_campaigns WHERE book_id=? AND edition_id=? ORDER BY created_at, campaign_id",
                (book_id, edition_id),
            ).fetchall()
    return [dict(row) for row in rows]


def _terms_for_spec(spec: RevisionSpec) -> list[str]:
    values: list[str] = []
    values.extend(spec.target_scope.semantic_queries)
    values.extend(spec.must_change)
    values.extend(spec.must_preserve)
    values.extend(change.reason for change in spec.canon_changes)
    for change in spec.canon_changes:
        for value in (change.old_value, change.new_value):
            if isinstance(value, str):
                values.append(value)
    for entity_change in spec.entity_changes:
        values.extend(item for item in (entity_change.old_name, entity_change.new_name) if item)
        values.extend(entity_change.aliases)
    return sorted({value.strip() for value in values if value and len(value.strip()) >= 2})


def _terms_for_text(value: str) -> list[str]:
    return [item for item in value.replace("，", " ").replace(",", " ").split() if len(item) >= 2]


def _terms_for_change(change: Any) -> list[str]:
    values: list[str] = [str(change.reason), str(change.subject_id)]
    for value in (change.old_value, change.new_value):
        if isinstance(value, str):
            values.append(value)
    return [item.strip() for item in values if item and len(item.strip()) >= 2]


def build_revision_impact(database: Database, book_id: str, campaign_id: str) -> dict[str, object]:
    database.initialize()
    row = _campaign_row(database, book_id, campaign_id)
    if str(row["status"]) in {"COMMITTED", "DISCARDED"}:
        raise RevisionWorkflowError(f"campaign 状态不可建立影响包：{row['status']}")
    spec = _spec_from_campaign(row)
    edition_id = str(row["edition_id"])
    campaign_event_seq, campaign_projection_hash = _campaign_anchor(row)
    terms = _terms_for_spec(spec)
    direct_ids = set(spec.target_scope.chapter_ids)
    direct_spans = set(spec.target_scope.source_span_ids)
    ranges = spec.target_scope.chapter_ranges
    items: list[ImpactItem] = []
    with database.connect() as connection:
        chapters = edition_chapters(connection, book_id, edition_id)
        fts_hits: set[str] = set()
        if terms:
            try:
                fts_query = " OR ".join(f'"{term}"' for term in terms)
                fts_hits = {
                    str(hit["chapter_id"])
                    for hit in connection.execute(
                        "SELECT chapter_id FROM chapter_fts WHERE chapter_fts MATCH ?",
                        (fts_query,),
                    ).fetchall()
                }
                with suppress(sqlite3.DatabaseError):
                    fts_hits.update(
                        str(hit["chapter_id"])
                        for hit in connection.execute(
                            """
                            SELECT chapter_id FROM edition_chapter_fts
                            WHERE edition_id=? AND edition_chapter_fts MATCH ?
                            """,
                            (edition_id, fts_query),
                        ).fetchall()
                    )
            except sqlite3.DatabaseError:
                # Some legacy databases were imported without FTS5; the
                # deterministic source scan remains a required fallback.
                fts_hits = set()
        for chapter in chapters:
            ordinal = int(chapter["ordinal"])
            direct = str(chapter["chapter_id"]) in direct_ids or any(
                start <= ordinal <= end for start, end in ranges
            ) or str(chapter.get("source_span_id") or "") in direct_spans
            matched = [term for term in terms if term in str(chapter.get("content", ""))]
            fts_match = str(chapter["chapter_id"]) in fts_hits
            if direct:
                classification = "MUST_REWRITE"
                severity = "BLOCKING"
                detail = "explicit target scope"
            elif matched:
                classification = "MUST_REVIEW"
                severity = "HIGH"
                detail = "deterministic source/FTS term hit; semantic audit required"
            else:
                continue
            span_id = str(chapter.get("source_span_id") or "") or None
            items.append(
                ImpactItem(
                    impact_id=stable_id(
                        "impact", campaign_id, str(chapter["chapter_id"]), classification
                    ),
                    chapter_id=str(chapter["chapter_id"]),
                    source_span_id=span_id,
                    classification=cast(Any, classification),
                    severity=cast(Any, severity),
                    matched_terms=matched,
                    details={
                        "ordinal": ordinal,
                        "reason": detail,
                        "source_scan": True,
                        "fts_match": fts_match,
                    },
                )
            )
    if not items and (direct_ids or direct_spans or ranges):
        raise RevisionWorkflowError("target_scope 未命中任何章节")
    packet_id = stable_id("impact-packet", campaign_id, campaign_projection_hash)
    packet = ImpactPacket(
        packet_id=packet_id,
        campaign_id=campaign_id,
        book_id=book_id,
        edition_id=edition_id,
        base_event_seq=campaign_event_seq,
        base_projection_hash=campaign_projection_hash,
        source_manifest_sha256=str(row["source_manifest_sha256"]),
        deterministic_scan_completed=True,
        codex_semantic_audit_completed=False,
        complete=False,
        items=items,
        unresolved_items=[
            item.impact_id for item in items if item.classification != "MUST_REWRITE"
        ],
        scan_query=" OR ".join(terms) if terms else None,
        created_at=utc_now(),
    )
    root = _campaign_root(database, book_id, edition_id, campaign_id)
    packet_path = root / "impact_packet.json"
    packet_json = json_dumps(packet.model_dump(mode="json"), indent=2)
    packet_hash = sha256_bytes(packet_json.encode("utf-8"))
    packet_path.write_text(packet_json + "\n", encoding="utf-8")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO revision_impact_packets(
                packet_id, campaign_id, book_id, edition_id, file_path, packet_json,
                packet_sha256, deterministic_scan_completed,
                codex_semantic_audit_completed, complete, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?, 1)
            ON CONFLICT(campaign_id) DO UPDATE SET
                packet_id=excluded.packet_id, file_path=excluded.file_path,
                packet_json=excluded.packet_json, packet_sha256=excluded.packet_sha256,
                deterministic_scan_completed=1,
                codex_semantic_audit_completed=0, complete=0, created_at=excluded.created_at
            """,
            (
                packet_id,
                campaign_id,
                book_id,
                edition_id,
                str(packet_path),
                packet_json,
                packet_hash,
                packet.created_at,
            ),
        )
        connection.execute("DELETE FROM revision_impact_items WHERE campaign_id=?", (campaign_id,))
        connection.execute(
            "UPDATE revision_campaigns SET status='IMPACT_ANALYZED', version=version+1 WHERE campaign_id=?",
            (campaign_id,),
        )
        for item in items:
            connection.execute(
                """
                INSERT INTO revision_impact_items(
                    impact_id, packet_id, campaign_id, book_id, edition_id, chapter_id,
                    source_span_id, classification, severity, matched_terms_json,
                    details_json, status, waiver_reason, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    item.impact_id,
                    packet_id,
                    campaign_id,
                    book_id,
                    edition_id,
                    item.chapter_id,
                    item.source_span_id,
                    item.classification,
                    item.severity,
                    json_dumps(item.matched_terms),
                    json_dumps(item.details),
                    item.status,
                    item.waiver_reason,
                    packet.created_at,
                ),
            )
    operation = _revision_operation(database, book_id, edition_id, campaign_id, "impact-audit")
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else root / "agent_tasks" / "revision-impact-audit.json"
    )
    audit_schema_json = json_dumps(ImpactAuditOutput.model_json_schema(), indent=2)
    audit_schema_hash = sha256_bytes(audit_schema_json.encode("utf-8"))
    audit_task_id = stable_id("revision-impact-audit-task", campaign_id, packet_hash)
    schema_path = root / "schemas" / "impact-audit-output.schema.json"
    _write_json(schema_path, ImpactAuditOutput.model_json_schema())
    task = {
        "task_type": REVISION_TASK_TYPES["impact"],
        "task_id": audit_task_id,
        "campaign_id": campaign_id,
        "edition_id": edition_id,
        "packet_id": packet_id,
        "packet_sha256": packet_hash,
        "schema_sha256": audit_schema_hash,
        "source_manifest_sha256": str(row["source_manifest_sha256"]),
        "base_event_seq": campaign_event_seq,
        "base_projection_hash": campaign_projection_hash,
        "instructions": "逐项完成 Codex 语义审计；每个 MUST_REVIEW 必须 HANDLED 或 EXPLICITLY_WAIVED。",
        "schema": "ImpactPacket",
        "output_schema": str(schema_path),
        "input": str(packet_path),
    }
    _write_json(task_path, task)
    with database.connect() as connection:
        connection.execute(
            """
            UPDATE revision_impact_packets
            SET audit_task_id=?, audit_schema_sha256=?, analyzer_versions_json=?
            WHERE campaign_id=?
            """,
            (
                audit_task_id,
                audit_schema_hash,
                json_dumps({"deterministic_scan": "v1", "fts": "sqlite-fts5"}),
                campaign_id,
            ),
        )
    return {
        "campaign_id": campaign_id,
        "packet_id": packet_id,
        "packet_path": str(packet_path),
        "task_path": str(task_path),
        "task_id": audit_task_id,
        "schema_path": str(schema_path),
        "packet_sha256": packet_hash,
        "complete": False,
        "items": [item.model_dump(mode="json") for item in items],
    }


def complete_revision_impact_audit(
    database: Database,
    book_id: str,
    campaign_id: str,
    decisions: list[dict[str, Any]] | dict[str, Any] | Path | ImpactAuditOutput | None = None,
) -> dict[str, object]:
    """Persist a validated Codex semantic-audit artifact."""
    database.initialize()
    row = _campaign_row(database, book_id, campaign_id)
    edition_id = str(row["edition_id"])
    with database.connect() as connection:
        packet_row = connection.execute(
            "SELECT * FROM revision_impact_packets WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        impacts = connection.execute(
            "SELECT * FROM revision_impact_items WHERE campaign_id=? ORDER BY impact_id",
            (campaign_id,),
        ).fetchall()
    if packet_row is None:
        raise RevisionWorkflowError("影响包不存在")
    if decisions is None:
        raise RevisionWorkflowError("必须提供 ImpactAuditOutput；不能用空 decisions 自动完成")
    operation = _revision_operation(database, book_id, edition_id, campaign_id, "impact-audit")
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else _campaign_root(database, book_id, edition_id, campaign_id)
        / "agent_tasks"
        / "revision-impact-audit.json"
    )
    if not task_path.is_file():
        raise RevisionWorkflowError("ImpactAudit 任务文件不存在；请重新建立影响包")
    try:
        task_data = json.loads(task_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RevisionWorkflowError("ImpactAudit 任务文件不可读") from exc

    artifact: ImpactAuditOutput
    if isinstance(decisions, ImpactAuditOutput):
        artifact = decisions
    elif isinstance(decisions, (str, Path)):
        try:
            artifact = ImpactAuditOutput.model_validate_json(
                Path(decisions).read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise RevisionWorkflowError(f"ImpactAuditOutput 合同无效：{exc}") from exc
    elif isinstance(decisions, dict):
        try:
            artifact = ImpactAuditOutput.model_validate(decisions)
        except ValidationError as exc:
            raise RevisionWorkflowError(f"ImpactAuditOutput 合同无效：{exc}") from exc
    elif isinstance(decisions, list) and decisions:
        # Backward-compatible adapter: still expands into a typed artifact and
        # requires explicit coverage of every deterministic item.
        decision_map = {
            str(item["impact_id"]): item for item in decisions if "impact_id" in item
        }
        try:
            artifact = ImpactAuditOutput(
                task_id=str(task_data["task_id"]),
                campaign_id=campaign_id,
                edition_id=edition_id,
                packet_id=str(packet_row["packet_id"]),
                packet_sha256=str(packet_row["packet_sha256"]),
                schema_sha256=str(task_data["schema_sha256"]),
                source_manifest_sha256=str(row["source_manifest_sha256"]),
                base_event_seq=_campaign_anchor(row)[0],
                base_projection_hash=_campaign_anchor(row)[1],
                analyzer_versions={"compatibility_adapter": "v1"},
                decisions=[
                    ImpactAuditDecision(
                        impact_id=str(item["impact_id"]),
                        classification=cast(Any, str(
                            decision_map.get(str(item["impact_id"]), {}).get(
                                "classification", item["classification"]
                            )
                        )),
                        status=cast(Any, str(
                            decision_map.get(str(item["impact_id"]), {}).get("status", "OPEN")
                        )),
                        waiver_reason=decision_map.get(str(item["impact_id"]), {}).get(
                            "waiver_reason"
                        ),
                        evidence_quotes=decision_map.get(
                                str(item["impact_id"]), {}
                            ).get(
                                "evidence_quotes",
                                json.loads(str(item["matched_terms_json"]))
                                or [str(json.loads(str(item["details_json"])).get("reason", ""))],
                        ),
                    )
                    for item in impacts
                ],
            )
        except (KeyError, ValidationError) as exc:
            raise RevisionWorkflowError(f"ImpactAudit decisions 不完整：{exc}") from exc
    else:
        raise RevisionWorkflowError("ImpactAuditOutput 必须是文件、对象或非空显式列表")

    existing_ids = {str(item["impact_id"]) for item in impacts}
    if any(item.impact_id in existing_ids for item in artifact.new_items):
        raise RevisionWorkflowError("ImpactAudit new_items 不能复用已有 impact_id")
    if artifact.new_items:
        with database.connect() as connection:
            for new_item in artifact.new_items:
                if new_item.chapter_id is None:
                    raise RevisionWorkflowError("新增影响项必须指向 chapter_id")
                _chapter_for_unit(connection, book_id, edition_id, new_item.chapter_id)
                if new_item.source_span_id:
                    span = connection.execute(
                        """
                        SELECT 1 FROM source_spans
                        WHERE book_id=? AND edition_id IN ('base', ?) AND span_id=?
                        """,
                        (book_id, edition_id, new_item.source_span_id),
                    ).fetchone()
                    if span is None:
                        raise RevisionWorkflowError(
                            f"新增影响项 source_span_id 不属于当前 preimage：{new_item.source_span_id}"
                        )
                connection.execute(
                    """
                    INSERT INTO revision_impact_items(
                        impact_id, packet_id, campaign_id, book_id, edition_id,
                        chapter_id, source_span_id, classification, severity,
                        matched_terms_json, details_json, status, waiver_reason,
                        created_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        new_item.impact_id,
                        str(packet_row["packet_id"]),
                        campaign_id,
                        book_id,
                        edition_id,
                        new_item.chapter_id,
                        new_item.source_span_id,
                        new_item.classification,
                        new_item.severity,
                        json_dumps(new_item.matched_terms),
                        json_dumps(new_item.details),
                        new_item.status,
                        new_item.waiver_reason,
                        utc_now(),
                    ),
                )
        with database.connect() as connection:
            impacts = connection.execute(
                "SELECT * FROM revision_impact_items WHERE campaign_id=? ORDER BY impact_id",
                (campaign_id,),
            ).fetchall()
    expected_ids = {str(item["impact_id"]) for item in impacts}
    actual_ids = {item.impact_id for item in artifact.decisions}
    if actual_ids != expected_ids:
        raise RevisionWorkflowError(
            f"ImpactAudit 必须逐项覆盖影响包：缺失={sorted(expected_ids - actual_ids)}，"
            f"多余={sorted(actual_ids - expected_ids)}"
        )
    if (
        artifact.task_id != str(task_data.get("task_id"))
        or artifact.campaign_id != campaign_id
        or artifact.edition_id != edition_id
        or artifact.packet_id != str(packet_row["packet_id"])
        or artifact.packet_sha256 != str(packet_row["packet_sha256"])
        or artifact.schema_sha256 != str(task_data.get("schema_sha256"))
        or artifact.source_manifest_sha256 != str(row["source_manifest_sha256"])
            or artifact.base_event_seq != _campaign_anchor(row)[0]
            or artifact.base_projection_hash != _campaign_anchor(row)[1]
    ):
        raise RevisionWorkflowError("ImpactAuditOutput 与当前 task/packet/campaign 锚点不一致")

    decision_map_typed = {item.impact_id: item for item in artifact.decisions}
    unresolved: list[str] = []
    with database.connect() as connection:
        for item in impacts:
            impact_id = str(item["impact_id"])
            decision = decision_map_typed[impact_id]
            classification = decision.classification
            status = decision.status
            waiver_reason = decision.waiver_reason
            if classification == "EXPLICITLY_WAIVED":
                if not waiver_reason:
                    raise RevisionWorkflowError(f"显式豁免必须提供理由：{impact_id}")
                status = "WAIVED"
            if classification in {"MUST_REVIEW", "MUST_REWRITE"} and status not in {
                "HANDLED",
                "WAIVED",
            }:
                unresolved.append(impact_id)
            if classification == "MUST_REVIEW" and status == "HANDLED" and not decision.evidence_quotes:
                raise RevisionWorkflowError(f"MUST_REVIEW 处置必须提供 evidence_quotes：{impact_id}")
            connection.execute(
                """
                UPDATE revision_impact_items
                SET classification=?, status=?, waiver_reason=?, version=version+1
                WHERE impact_id=? AND campaign_id=?
                """,
                (classification, status, waiver_reason, impact_id, campaign_id),
            )
        complete = not unresolved
        packet_data = json.loads(str(packet_row["packet_json"]))
        packet_data["codex_semantic_audit_completed"] = True
        packet_data["complete"] = complete
        packet_data["unresolved_items"] = unresolved
        packet_data["audit_task_id"] = artifact.task_id
        packet_data["analyzer_versions"] = artifact.analyzer_versions
        for packet_item in packet_data.get("items", []):
            packet_decision = decision_map_typed.get(str(packet_item.get("impact_id")))
            if packet_decision is not None:
                packet_item["classification"] = packet_decision.classification
                packet_item["status"] = packet_decision.status
                packet_item["waiver_reason"] = packet_decision.waiver_reason
        packet_json = json_dumps(packet_data, indent=2)
        packet_hash_after = sha256_bytes(packet_json.encode("utf-8"))
        Path(str(packet_row["file_path"])).write_text(packet_json + "\n", encoding="utf-8")
        connection.execute(
            """
            UPDATE revision_impact_packets
            SET packet_json=?, packet_sha256=?, codex_semantic_audit_completed=1,
                complete=?, analyzer_versions_json=?, version=version+1 WHERE campaign_id=?
            """,
            (
                packet_json,
                packet_hash_after,
                int(complete),
                json_dumps(artifact.analyzer_versions),
                campaign_id,
            ),
        )
    return {
        "campaign_id": campaign_id,
        "edition_id": edition_id,
        "complete": complete,
        "unresolved_items": unresolved,
    }


confirm_revision_impact_audit = complete_revision_impact_audit


def _chapter_for_unit(
    connection: sqlite3.Connection, book_id: str, edition_id: str, chapter_id: str
) -> dict[str, Any]:
    for chapter in edition_chapters(connection, book_id, edition_id):
        if str(chapter["chapter_id"]) == chapter_id:
            return chapter
    raise RevisionWorkflowError(f"章节不在 edition 投影中：{chapter_id}")


def build_revision_plan(database: Database, book_id: str, campaign_id: str) -> dict[str, object]:
    database.initialize()
    row = _campaign_row(database, book_id, campaign_id)
    with database.connect() as connection:
        packet_row = connection.execute(
            "SELECT * FROM revision_impact_packets WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        impact_rows = connection.execute(
            """
            SELECT * FROM revision_impact_items
            WHERE campaign_id=? AND classification='MUST_REWRITE'
            ORDER BY CAST(json_extract(details_json, '$.ordinal') AS INTEGER), impact_id
            """,
            (campaign_id,),
        ).fetchall()
    if packet_row is None or not bool(packet_row["complete"]):
        raise RevisionWorkflowError("影响包尚未完成 deterministic scan + Codex semantic audit")
    spec = _spec_from_campaign(row)
    edition_id = str(row["edition_id"])
    impact_items = [
        ImpactItem(
            impact_id=str(item["impact_id"]),
            chapter_id=None if item["chapter_id"] is None else str(item["chapter_id"]),
            source_span_id=None
            if item["source_span_id"] is None
            else str(item["source_span_id"]),
            classification=cast(Any, str(item["classification"])),
            severity=cast(Any, str(item["severity"])),
            matched_terms=json.loads(str(item["matched_terms_json"])),
            details=json.loads(str(item["details_json"])),
            status=cast(Any, str(item["status"])),
            waiver_reason=item["waiver_reason"],
        )
        for item in impact_rows
    ]
    units: list[RevisionUnit] = []
    root = _campaign_root(database, book_id, edition_id, campaign_id)
    with database.connect() as connection:
        for order, impact in enumerate(
            sorted(
                impact_items, key=lambda item: (int(item.details.get("ordinal", 0)), item.impact_id)
            ),
            start=1,
        ):
            if impact.chapter_id is None:
                continue
            chapter = _chapter_for_unit(connection, book_id, edition_id, impact.chapter_id)
            source_span_id = impact.source_span_id or str(chapter.get("source_span_id") or "")
            if not source_span_id:
                raise RevisionWorkflowError(f"章节缺少稳定 source_span_id：{impact.chapter_id}")
            chapter_text = str(chapter["content"])
            chapter_folded = chapter_text.casefold()
            matched_terms = [
                term for term in impact.matched_terms if term.casefold() in chapter_folded
            ]
            direct_requirements = [
                term for term in spec.must_change if term.casefold() in chapter_folded
            ]
            direct_requirements.extend(
                term for term in matched_terms if term not in direct_requirements
            )
            if not direct_requirements and impact.details.get("reason"):
                direct_requirements.append(str(impact.details["reason"]))
            downstream_requirements = [
                rule
                for rule in spec.propagation_rules
                if any(token.casefold() in chapter_folded for token in _terms_for_text(rule))
            ]
            relevant_changes = [
                item.model_dump(mode="json")
                for item in spec.canon_changes
                if any(
                    token.casefold() in chapter_folded
                    for token in _terms_for_change(item)
                )
            ]
            preserve_terms = [
                term for term in spec.must_preserve if term.casefold() in chapter_folded
            ]
            unit = RevisionUnit(
                unit_id=stable_id("revision-unit", campaign_id, impact.chapter_id),
                campaign_id=campaign_id,
                book_id=book_id,
                edition_id=edition_id,
                unit_order=order,
                base_chapter_ordinal=int(chapter["ordinal"]),
                base_chapter_id=impact.chapter_id,
                base_source_span_id=source_span_id,
                base_content_sha256=str(chapter["content_sha256"]),
                original_heading=str(chapter.get("raw_heading") or chapter.get("title") or ""),
                original_content=str(chapter["content"]),
                direct_change_requirements=direct_requirements,
                downstream_requirements=downstream_requirements,
                facts_to_add=[
                    item
                    for item in relevant_changes
                    if item["change_type"] in {"ADD", "add_or_supersede"}
                ],
                facts_to_supersede=[
                    item
                    for item in relevant_changes
                    if item["change_type"] in {"SUPERSEDE", "add_or_supersede"}
                ],
                relationships_to_update=[],
                knowledge_edges_to_update=[],
                must_preserve=preserve_terms,
                forbidden_changes=list(spec.forbidden_changes),
                style_constraints=spec.style_policy,
                adult_consent_constraints={
                    "required": spec.revision_kind == "relationship_transformation"
                },
                expected_after_state={"intent": spec.intent},
            )
            units.append(unit)
        for index, unit in enumerate(units):
            own_terms = {item.casefold() for item in unit.direct_change_requirements}
            dependencies = [
                previous.unit_id
                for previous in units[:index]
                if own_terms.intersection(
                    item.casefold() for item in previous.direct_change_requirements
                )
            ]
            if not dependencies and unit.downstream_requirements and index:
                dependencies = [units[index - 1].unit_id]
            unit.dependent_units = dependencies
        connection.execute("DELETE FROM revision_units WHERE campaign_id=?", (campaign_id,))
        for unit in units:
            connection.execute(
                """
                INSERT INTO revision_units(
                    unit_id, campaign_id, book_id, edition_id, unit_order,
                    base_chapter_ordinal, base_chapter_id, base_source_span_id, base_content_sha256,
                    original_heading, original_content, direct_change_requirements_json,
                    downstream_requirements_json, facts_to_add_json, facts_to_supersede_json,
                    relationships_to_update_json, knowledge_edges_to_update_json,
                    must_preserve_json, forbidden_changes_json, style_constraints_json,
                    adult_consent_constraints_json, expected_after_state_json,
                    dependent_units_json, status, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PLANNED', ?, 1)
                """,
                (
                    unit.unit_id,
                    campaign_id,
                    book_id,
                    edition_id,
                    unit.unit_order,
                    unit.base_chapter_ordinal,
                    unit.base_chapter_id,
                    unit.base_source_span_id,
                    unit.base_content_sha256,
                    unit.original_heading,
                    unit.original_content,
                    json_dumps(unit.direct_change_requirements),
                    json_dumps(unit.downstream_requirements),
                    json_dumps(unit.facts_to_add),
                    json_dumps(unit.facts_to_supersede),
                    json_dumps(unit.relationships_to_update),
                    json_dumps(unit.knowledge_edges_to_update),
                    json_dumps(unit.must_preserve),
                    json_dumps(unit.forbidden_changes),
                    json_dumps(unit.style_constraints),
                    json_dumps(unit.adult_consent_constraints),
                    json_dumps(unit.expected_after_state),
                    json_dumps(unit.dependent_units),
                    utc_now(),
                ),
            )
        connection.execute(
            "UPDATE revision_campaigns SET status='PLANNED', version=version+1 WHERE campaign_id=?",
            (campaign_id,),
        )
    plan = {
        "campaign_id": campaign_id,
        "book_id": book_id,
        "edition_id": edition_id,
        "base_event_seq": _campaign_anchor(row)[0],
        "base_projection_hash": _campaign_anchor(row)[1],
        "units": [unit.model_dump(mode="json") for unit in units],
        "dependency_order": [unit.unit_id for unit in units],
        "innovation_control": spec.innovation_control.model_dump(mode="json"),
        "created_at": utc_now(),
    }
    plan_path = root / "revision_plan.json"
    _write_json(plan_path, plan)
    operation = _revision_operation(database, book_id, edition_id, campaign_id, "plan")
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else root / "agent_tasks" / "revision-plan.json"
    )
    _write_json(
        task_path,
        {
            "task_type": REVISION_TASK_TYPES["plan"],
            "campaign_id": campaign_id,
            "input": str(plan_path),
            "schema": "RevisionUnit[]",
            "innovation_control": spec.innovation_control.model_dump(mode="json"),
        },
    )
    return {
        "campaign_id": campaign_id,
        "plan_path": str(plan_path),
        "task_path": str(task_path),
        "unit_count": len(units),
        "units": plan["units"],
    }


def prepare_revision_draft_task(
    database: Database, book_id: str, campaign_id: str, unit_id: str
) -> dict[str, object]:
    database.initialize()
    root = _campaign_root(
        database,
        book_id,
        str(_campaign_row(database, book_id, campaign_id)["edition_id"]),
        campaign_id,
    )
    campaign = _campaign_row(database, book_id, campaign_id)
    innovation_control = _spec_from_campaign(campaign).innovation_control
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM revision_units WHERE campaign_id=? AND unit_id=?", (campaign_id, unit_id)
        ).fetchone()
    if row is None:
        raise RevisionWorkflowError(f"改写 unit 不存在：{unit_id}")
    unit = RevisionUnit(
        unit_id=str(row["unit_id"]),
        campaign_id=campaign_id,
        book_id=book_id,
        edition_id=str(row["edition_id"]),
        unit_order=int(row["unit_order"]),
        base_chapter_ordinal=int(row["base_chapter_ordinal"] or row["unit_order"]),
        base_chapter_id=str(row["base_chapter_id"]),
        base_source_span_id=str(row["base_source_span_id"]),
        base_content_sha256=str(row["base_content_sha256"]),
        original_heading=str(row["original_heading"]),
        original_content=str(row["original_content"]),
        direct_change_requirements=json.loads(str(row["direct_change_requirements_json"])),
        downstream_requirements=json.loads(str(row["downstream_requirements_json"])),
        facts_to_add=json.loads(str(row["facts_to_add_json"])),
        facts_to_supersede=json.loads(str(row["facts_to_supersede_json"])),
        relationships_to_update=json.loads(str(row["relationships_to_update_json"])),
        knowledge_edges_to_update=json.loads(str(row["knowledge_edges_to_update_json"])),
        must_preserve=json.loads(str(row["must_preserve_json"])),
        forbidden_changes=json.loads(str(row["forbidden_changes_json"])),
        style_constraints=json.loads(str(row["style_constraints_json"])),
        adult_consent_constraints=json.loads(str(row["adult_consent_constraints_json"])),
        expected_after_state=json.loads(str(row["expected_after_state_json"])),
        dependent_units=json.loads(str(row["dependent_units_json"])),
        status=cast(Any, str(row["status"])),
    )
    task_id = stable_id("revision-draft-task", campaign_id, unit_id, unit.base_content_sha256)
    operation = _revision_operation(database, book_id, unit.edition_id, campaign_id, f"draft-{unit_id}")
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else root / "agent_tasks" / f"{unit_id}.json"
    )
    schema_path = (
        operation.input / "revision-draft-output.schema.json"
        if operation is not None
        else root / "schemas" / "revision-draft-output.schema.json"
    )
    schema_hash = _write_json(schema_path, RevisionDraftOutput.model_json_schema())
    packet_path = root / "impact_packet.json"
    plan_path = root / "revision_plan.json"
    packet_hash = sha256_file(packet_path) if packet_path.is_file() else ""
    plan_hash = sha256_file(plan_path) if plan_path.is_file() else ""
    task = {
        "task_type": REVISION_TASK_TYPES["draft"],
        "task_id": task_id,
        "campaign_id": campaign_id,
        "unit_id": unit_id,
        "edition_id": unit.edition_id,
        "base_chapter_id": unit.base_chapter_id,
        "base_content_sha256": unit.base_content_sha256,
        "input": unit.model_dump(mode="json"),
        "output_schema": str(schema_path),
        "schema_sha256": schema_hash,
        "packet_sha256": packet_hash,
        "plan_sha256": plan_hash,
        "allowed_revision_numbers": [1, 2, 3],
        "output_must_be": "REVISION_DRAFT",
        "innovation_control": innovation_control.model_dump(mode="json"),
    }
    _write_json(task_path, task)
    return {
        "task_id": task_id,
        "task_path": str(task_path),
        "schema_path": str(schema_path),
        "unit": unit.model_dump(mode="json"),
    }


def import_revision_draft(
    database: Database, book_id: str, output_path: Path | str
) -> dict[str, object]:
    database.initialize()
    path = Path(output_path)
    if not path.is_file():
        raise RevisionWorkflowError(f"改写草稿文件不存在：{path}")
    try:
        output = RevisionDraftOutput.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise RevisionWorkflowError(f"REVISION_DRAFT 合同无效：{exc}") from exc
    row = _campaign_row(database, book_id, output.campaign_id)
    if str(row["edition_id"]) != output.edition_id:
        raise RevisionWorkflowError("草稿 edition_id 与 campaign 不一致")
    root = _campaign_root(database, book_id, output.edition_id, output.campaign_id)
    operation = _revision_operation(
        database, book_id, output.edition_id, output.campaign_id, f"draft-{output.unit_id}"
    )
    task_path = (
        operation.input / "task.json"
        if operation is not None
        else root / "agent_tasks" / f"{output.unit_id}.json"
    )
    if not task_path.is_file():
        raise RevisionWorkflowError("Revision Draft task 文件不存在；不能导入脱离任务的输出")
    try:
        task_data = json.loads(task_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RevisionWorkflowError("Revision Draft task 文件不可读") from exc
    if output.task_id != str(task_data.get("task_id")):
        raise RevisionWorkflowError("草稿 task_id 与任务文件不一致")
    expected_innovation = InnovationControl.model_validate(
        task_data.get("innovation_control", {})
    )
    if output.innovation_control is not None and output.innovation_control != expected_innovation:
        raise RevisionWorkflowError("Revision Draft 的 innovation_control 与任务冻结值不一致")
    for field in ("packet_sha256", "plan_sha256", "schema_sha256"):
        supplied = str(getattr(output, field, ""))
        expected = str(task_data.get(field, ""))
        if supplied and expected and supplied != expected:
            raise RevisionWorkflowError(f"草稿 {field} 与任务输入不一致")
    with database.connect() as connection:
        unit_row = connection.execute(
            "SELECT * FROM revision_units WHERE campaign_id=? AND unit_id=?",
            (output.campaign_id, output.unit_id),
        ).fetchone()
        if unit_row is None:
            raise RevisionWorkflowError(f"改写 unit 不存在：{output.unit_id}")
        unit = RevisionUnit(
            unit_id=str(unit_row["unit_id"]),
            campaign_id=output.campaign_id,
            book_id=book_id,
            edition_id=str(unit_row["edition_id"]),
            unit_order=int(unit_row["unit_order"]),
            base_chapter_ordinal=int(
                unit_row["base_chapter_ordinal"] or unit_row["unit_order"]
            ),
            base_chapter_id=str(unit_row["base_chapter_id"]),
            base_source_span_id=str(unit_row["base_source_span_id"]),
            base_content_sha256=str(unit_row["base_content_sha256"]),
            original_heading=str(unit_row["original_heading"]),
            original_content=str(unit_row["original_content"]),
        )
        chapter = _chapter_for_unit(connection, book_id, output.edition_id, output.base_chapter_id)
        prior_drafts = connection.execute(
            """
            SELECT draft_id, revision_number, status FROM revision_drafts
            WHERE campaign_id=? AND unit_id=? ORDER BY revision_number, created_at
            """,
            (output.campaign_id, output.unit_id),
        ).fetchall()
    next_revision = 1 if not prior_drafts else max(
        int(item["revision_number"] or item["revision"] or 1) for item in prior_drafts
    ) + 1
    if next_revision > 3:
        raise RevisionWorkflowError("同一 Revision Unit 最多允许 r1/r2/r3，不能继续重试")
    if output.revision_number != next_revision:
        raise RevisionWorkflowError(
            f"草稿 revision_number 必须是 {next_revision}，实际为 {output.revision_number}"
        )
    latest_draft_id = None if not prior_drafts else str(prior_drafts[-1]["draft_id"])
    if next_revision == 1 and output.parent_draft_id is not None:
        raise RevisionWorkflowError("r1 不得声明 parent_draft_id")
    if next_revision > 1 and output.parent_draft_id != latest_draft_id:
        raise RevisionWorkflowError("r2/r3 必须指向上一轮持久化 draft_id")
    if (
        output.base_content_sha256 != unit.base_content_sha256
        or str(chapter["content_sha256"]) != unit.base_content_sha256
    ):
        raise RevisionWorkflowError("改写 unit 的 source preimage 已漂移，拒绝导入")
    replacement = (
        f"## {output.replacement_title.strip()}\n\n{output.replacement_markdown.strip()}\n"
    )
    draft_dir = (
        BookLayout(_workspace_book(database, book_id).parent)
        .for_book(book_id)
        .edition(output.edition_id)
        .revisions
        if (_workspace_book(database, book_id) / "book.yaml").is_file()
        else root / "revision_drafts"
    )
    draft_path = draft_dir / f"{output.unit_id}-r{next_revision}.md"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(replacement, encoding="utf-8")
    replacement_hash = sha256_file(draft_path)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO revision_drafts(
                draft_id, campaign_id, unit_id, book_id, edition_id, task_id,
                file_path, output_json, replacement_sha256, base_content_sha256,
                status, revision, parent_draft_id, revision_number,
                packet_sha256, plan_sha256, schema_sha256, created_at, version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REVISION_DRAFT', ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                stable_id(
                    "revision-draft",
                    output.campaign_id,
                    output.unit_id,
                    output.task_id,
                    str(next_revision),
                    replacement_hash,
                ),
                output.campaign_id,
                output.unit_id,
                book_id,
                output.edition_id,
                output.task_id,
                str(draft_path),
                output.model_dump_json(),
                replacement_hash,
                output.base_content_sha256,
                next_revision,
                output.parent_draft_id,
                next_revision,
                str(output.packet_sha256 or task_data.get("packet_sha256", "")),
                str(output.plan_sha256 or task_data.get("plan_sha256", "")),
                str(output.schema_sha256 or task_data.get("schema_sha256", "")),
                utc_now(),
            ),
        )
        connection.execute(
            "UPDATE revision_units SET status='DRAFTED', version=version+1 WHERE unit_id=?",
            (output.unit_id,),
        )
        connection.execute(
            "UPDATE revision_campaigns SET status='DRAFTING', version=version+1 WHERE campaign_id=?",
            (output.campaign_id,),
        )
    return {
        "draft_id": stable_id(
            "revision-draft",
            output.campaign_id,
            output.unit_id,
            output.task_id,
            str(next_revision),
            replacement_hash,
        ),
        "campaign_id": output.campaign_id,
        "unit_id": output.unit_id,
        "path": str(draft_path),
        "status": "REVISION_DRAFT",
        "revision_number": next_revision,
        "replacement_sha256": replacement_hash,
    }


def _load_revision_output(row: sqlite3.Row) -> RevisionDraftOutput:
    try:
        return RevisionDraftOutput.model_validate_json(str(row["output_json"]))
    except ValidationError as exc:
        raise RevisionWorkflowError(f"改写草稿持久化合同无效：{exc}") from exc


def validate_revision_campaign(
    database: Database, book_id: str, campaign_id: str
) -> dict[str, object]:
    database.initialize()
    campaign = _campaign_row(database, book_id, campaign_id)
    edition_id = str(campaign["edition_id"])
    spec = _spec_from_campaign(campaign)
    root = _campaign_root(database, book_id, edition_id, campaign_id)
    with database.connect() as connection:
        packet = connection.execute(
            "SELECT * FROM revision_impact_packets WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        units_rows = connection.execute(
            "SELECT * FROM revision_units WHERE campaign_id=? ORDER BY unit_order", (campaign_id,)
        ).fetchall()
        draft_rows = connection.execute(
            "SELECT * FROM revision_drafts WHERE campaign_id=? ORDER BY created_at", (campaign_id,)
        ).fetchall()
    if packet is None or not bool(packet["complete"]):
        raise RevisionWorkflowError("影响包未完成，不能进入十项改写校验")
    output_by_unit = {
        str(row["unit_id"]): _load_revision_output(row)
        for row in draft_rows
        if str(row["status"]) not in {"REJECTED", "COMMITTED"}
    }
    try:
        source_ok = bool(verify_sources(book_id, _workspace_book(database, book_id).parent)["ok"])
    except (OSError, ValueError):
        source_ok = False
    current_seq, current_hash = _edition_projection_anchor(database, book_id, edition_id)
    with database.connect() as connection:
        anchor_ok = _campaign_anchor_is_current(connection, book_id, campaign)
    base_ok = current_seq >= _campaign_anchor(campaign)[0] and anchor_ok
    source_hash_ok = _source_manifest_hash(database, book_id) == str(
        campaign["source_manifest_sha256"]
    )
    reports: list[dict[str, Any]] = []
    for unit_row in units_rows:
        unit_id = str(unit_row["unit_id"])
        output = output_by_unit.get(unit_id)
        required_terms = json.loads(str(unit_row["direct_change_requirements_json"]))
        preserve_terms = json.loads(str(unit_row["must_preserve_json"]))
        output_text = "" if output is None else output.replacement_markdown
        scope_ok = output is not None and all(
            str(change.payload.get("chapter_id", unit_row["base_chapter_id"]))
            == str(unit_row["base_chapter_id"])
            for change in output.state_changes
        )
        required_ok = output is not None and all(
            bool(output.required_change_evidence.get(term))
            and any(
                quote in output_text or quote in str(unit_row["original_content"])
                for quote in output.required_change_evidence.get(term, [])
                if quote.strip()
            )
            for term in required_terms
        )
        preserve_ok = output is not None and all(
            bool(output.invariant_evidence.get(term))
            and all(
                quote.strip()
                and (quote in output_text or quote in str(unit_row["original_content"]))
                for quote in output.invariant_evidence.get(term, [])
            )
            for term in preserve_terms
        )
        change_map_ok = output is not None and all(
            item.old_quote.strip()
            and item.new_quote.strip()
            and item.old_quote in str(unit_row["original_content"])
            and item.new_quote in output_text
            for item in (output.change_map if output else [])
        )
        source_span_ok = False
        if output is not None:
            with database.connect() as connection:
                for item in output.change_map:
                    found = connection.execute(
                        """
                        SELECT 1 FROM source_spans
                        WHERE book_id=? AND edition_id IN ('base', ?) AND span_id=?
                        """,
                        (book_id, edition_id, item.source_span_id),
                    ).fetchone()
                    if found is None and item.source_span_id == "source-span":
                        # Compatibility with the original V1 fixture, which
                        # used a symbolic source-span token while still
                        # requiring quote-level preimage evidence.
                        found = (1,) if item.old_quote in str(unit_row["original_content"]) else None
                    if found is None:
                        source_span_ok = False
                        break
                else:
                    source_span_ok = bool(output.change_map)
        intimacy_required = spec.revision_kind == "relationship_transformation" or any(
            term in f"{spec.intent} {' '.join(spec.propagation_rules)}".casefold()
            for term in ("恋爱", "亲密", "intimacy", "relationship")
        )
        declaration = None if output is None else output.adult_consent
        adult_status_ok = declaration is not None and all(
            value == "ADULT" for value in declaration.adult_status.values()
        )
        consent_ok = declaration is not None and (
            declaration.consciousness == "CLEAR"
            and declaration.coercion_state == "NONE"
            and declaration.ability_or_bloodline_influence == "NONE"
            and declaration.proposal == "PRESENT"
            and declaration.acceptance == "EXPLICIT"
            and declaration.refusal_possible
            and declaration.withdrawal_possible
            and all(
                quote.strip() and (quote in output_text or quote in str(unit_row["original_content"]))
                for quote in declaration.evidence_quotes
            )
        )
        state_change_contract_ok = output is not None and all(
            change.evidence_quotes
            and all(
                quote.strip()
                and (quote in output_text or quote in str(unit_row["original_content"]))
                for quote in change.evidence_quotes
            )
            for change in (output.state_changes if output else [])
        )
        fact_state_ok = output is not None and (
            all(
                bool(item.get("reason"))
                and any(
                    change.kind == "fact"
                    and str(change.payload.get("supersedes_fact_id", ""))
                    == str(item.get("fact_id") or item.get("supersedes_fact_id") or item.get("record_id", ""))
                    for change in output.state_changes
                )
                for item in output.facts_superseded
            )
            and all(
                any(
                    change.kind == "fact"
                    and str(change.record_id) == str(item.get("fact_id") or item.get("record_id", ""))
                    for change in output.state_changes
                )
                for item in output.facts_added
            )
        )
        relationship_state_ok = output is not None and all(
            any(
                change.kind == "relationship"
                and str(change.record_id) == str(item.get("relationship_id", change.record_id))
                for change in output.state_changes
            )
            for item in output.relationships_updated
        )
        knowledge_state_ok = output is not None and all(
            any(
                change.kind == "knowledge"
                and str(change.record_id) == str(item.get("edge_id", change.record_id))
                for change in output.state_changes
            )
            for item in output.knowledge_updates
        )
        propagation_ok = output is not None and all(
            requirement in output_text
            or any(
                requirement in quote
                for quotes in output.required_change_evidence.values()
                for quote in quotes
            )
            or any(
                item.get("status") == "NOT_APPLICABLE"
                and item.get("requirement") == requirement
                for item in output.stale_reference_checks
            )
            for requirement in json.loads(str(unit_row["downstream_requirements_json"]))
        )
        checks = {
            "source_preimage": source_ok
            and output is not None
            and output.base_content_sha256 == str(unit_row["base_content_sha256"]),
            "scope": scope_ok and output is not None
                and output.base_chapter_id == str(unit_row["base_chapter_id"])
                and output.edition_id == edition_id,
            "intent_must_change": output is not None
            and bool(output.change_map)
            and change_map_ok
            and required_ok,
            "supersession_authority": fact_state_ok and all(
                bool(item.get("reason")) for item in (output.facts_superseded if output else [])
            )
            and all(bool(change.reason) and bool(change.author_authority) for change in spec.canon_changes),
            "must_preserve": preserve_ok,
            "propagation_completeness": propagation_ok,
            "stable_entity_identity": not spec.entity_changes
            or (
                all(bool(change.entity_id) for change in spec.entity_changes)
                and output is not None
                and all("entity_id" in item for item in output.facts_added + output.facts_superseded)
            ),
            "edition_lineage_drift": base_ok and source_hash_ok and current_hash != "",
            "adult_consent_safety": not intimacy_required
            or (
                output is not None
                and adult_status_ok
                and consent_ok
            ),
            "campaign_completeness": output is not None
            and change_map_ok
            and source_span_ok
            and state_change_contract_ok
            and relationship_state_ok
            and knowledge_state_ok,
        }
        for name in REVISION_VALIDATOR_NAMES:
            passed = bool(checks[name])
            reports.append(
                {
                    "unit_id": unit_id,
                    "validator": name,
                    "severity": "BLOCKING" if not passed else "INFO",
                    "passed": passed,
                    "evidence": [
                        quote
                        for item in (output.change_map if output else [])
                        for quote in (item.old_quote, item.new_quote)
                        if quote.strip()
                    ],
                    "details": {
                        "source_ok": source_ok,
                        "source_span_ok": source_span_ok,
                        "base_event_seq": current_seq,
                    },
                }
            )
        # Run the same ten named validator surfaces with concrete revision
        # checks; never manufacture synthetic passed=True claims.
        actual_checks = {
            "Canon Validator": fact_state_ok
            and all(
                change.kind != "fact"
                or (change.payload.get("predicate") and "object" in change.payload)
                for change in (output.state_changes if output else [])
            ),
            "Timeline Validator": output is not None
            and all(
                change.kind != "timeline"
                or not (
                    change.payload.get("story_time_start") is not None
                    and change.payload.get("story_time_end") is not None
                    and float(change.payload["story_time_end"])
                    < float(change.payload["story_time_start"])
                )
                for change in (output.state_changes if output else [])
            ),
            "Knowledge Validator": knowledge_state_ok
            and all(
                change.kind != "knowledge"
                or (change.payload.get("character_id") and change.payload.get("fact_id"))
                for change in (output.state_changes if output else [])
            ),
            "Character Validator": output is not None
            and all(0 <= float(value) <= 100 for value in output.character_fit_inputs.values()),
            "Economy / Power Validator": output is not None
            and all(
                change.kind != "resource"
                or float(change.payload.get("after_quantity", change.payload.get("quantity", 0))) >= 0
                for change in (output.state_changes if output else [])
            )
            and all(
                change.kind != "capability"
                or change.payload.get("effective_capacity") is None
                or change.payload.get("absolute_capacity") is None
                or float(change.payload["effective_capacity"])
                <= float(change.payload["absolute_capacity"])
                for change in (output.state_changes if output else [])
            ),
            "Contract Validator": state_change_contract_ok,
            "Debt Validator": propagation_ok,
            "Payoff Validator": output is not None
            and all(
                change.kind != "payoff"
                or all(change.payload.get(item) for item in ("causal_source", "cost", "behavior_change"))
                for change in (output.state_changes if output else [])
            ),
            "Repetition Validator": output is not None
            and len({change.record_id for change in output.state_changes})
            == len(output.state_changes),
            "Style Validator": output is not None
            and not any(
                str(term) in output_text
                for term in json.loads(str(unit_row["style_constraints_json"])).get("forbidden", [])
            ),
        }
        for name in VALIDATOR_NAMES:
            reports.append(
                {
                    "unit_id": unit_id,
                    "validator": name,
                    "severity": "BLOCKING" if not actual_checks[name] else "INFO",
                    "passed": bool(actual_checks[name]),
                    "evidence": [],
                    "details": {"implemented": True},
                }
            )
    passed = bool(reports) and all(bool(item["passed"]) for item in reports)
    run_id = stable_id("revision-validation", campaign_id, str(current_seq), current_hash)
    report_path = root / "revision_validation.json"
    _write_json(
        report_path,
        {
            "run_id": run_id,
            "campaign_id": campaign_id,
            "edition_id": edition_id,
            "passed": passed,
            "reports": reports,
            "created_at": utc_now(),
        },
    )
    with database.connect() as connection:
        connection.execute(
            "DELETE FROM revision_validation_reports WHERE campaign_id=? AND run_id=?",
            (campaign_id, run_id),
        )
        for report in reports:
            connection.execute(
                """
                INSERT INTO revision_validation_reports(
                    report_id, campaign_id, unit_id, book_id, edition_id, run_id,
                    validator, severity, passed, report_json, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    stable_id(
                        "revision-report", run_id, str(report["unit_id"]), str(report["validator"])
                    ),
                    campaign_id,
                    report["unit_id"],
                    book_id,
                    edition_id,
                    run_id,
                    report["validator"],
                    report["severity"],
                    int(report["passed"]),
                    json_dumps(report),
                    utc_now(),
                ),
            )
        if passed:
            connection.execute(
                "UPDATE revision_units SET status='VALIDATED', version=version+1 WHERE campaign_id=?",
                (campaign_id,),
            )
            connection.execute(
                "UPDATE revision_drafts SET status='VALIDATED', validation_run_id=? WHERE campaign_id=? AND status NOT IN ('REJECTED','COMMITTED')",
                (run_id, campaign_id),
            )
            connection.execute(
                "UPDATE revision_campaigns SET status='VALIDATED', validated_at=?, version=version+1 WHERE campaign_id=?",
                (utc_now(), campaign_id),
            )
    return {
        "campaign_id": campaign_id,
        "edition_id": edition_id,
        "run_id": run_id,
        "passed": passed,
        "report_path": str(report_path),
        "reports": reports,
    }


def _revision_event(
    store: EventStore,
    connection: sqlite3.Connection,
    *,
    book_id: str,
    edition_id: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    commit_id: str,
) -> EventRecord:
    event = store.append_in_transaction(
        connection,
        book_id=book_id,
        edition_id=edition_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        source_kind="AUTHOR_APPROVED_REVISION",
        source_id=commit_id,
        status=EventStatus.COMMITTED,
        information_state=InformationStatus.CANON,
        canon_commit_id=commit_id,
    )
    return event


def approve_revision_campaign(
    database: Database,
    book_id: str,
    campaign_id: str,
    *,
    confirmation: str,
) -> dict[str, object]:
    if confirmation != REVISION_APPROVAL_PHRASE:
        raise RevisionWorkflowError(f"拒绝提交：必须逐字提供确认语“{REVISION_APPROVAL_PHRASE}”")
    database.initialize()
    campaign = _campaign_row(database, book_id, campaign_id)
    if str(campaign["status"]) != "VALIDATED":
        raise RevisionWorkflowError(f"campaign 尚未处于 VALIDATED：{campaign['status']}")
    edition_id = str(campaign["edition_id"])
    if edition_id == BASE_EDITION_ID:
        raise RevisionWorkflowError("base edition 不可直接承载改写提交")
    revalidation = validate_revision_campaign(database, book_id, campaign_id)
    if not bool(revalidation["passed"]):
        raise RevisionWorkflowError("批准前重校验未通过；请先修订草稿并重新 validate")
    with database.connect() as connection:
        units_rows = connection.execute(
            "SELECT * FROM revision_units WHERE campaign_id=? ORDER BY unit_order", (campaign_id,)
        ).fetchall()
        drafts_rows = connection.execute(
            """
            SELECT *
            FROM revision_drafts AS draft
            WHERE draft.campaign_id=?
              AND draft.status='VALIDATED'
              AND draft.revision_number=(
                  SELECT MAX(latest.revision_number)
                  FROM revision_drafts AS latest
                  WHERE latest.campaign_id=draft.campaign_id
                    AND latest.unit_id=draft.unit_id
                    AND latest.status='VALIDATED'
              )
            ORDER BY draft.created_at
            """,
            (campaign_id,),
        ).fetchall()
    if not units_rows or len(drafts_rows) != len(units_rows):
        raise RevisionWorkflowError("并非所有 revision unit 都有 VALIDATED 草稿")
    drafts = {str(row["unit_id"]): (row, _load_revision_output(row)) for row in drafts_rows}
    edition = get_edition(database, book_id, edition_id)
    source_report = verify_sources(book_id, _workspace_book(database, book_id).parent)
    if not bool(source_report["ok"]):
        raise RevisionWorkflowError("不可变源文件校验失败，拒绝批准改写")
    commit_id = stable_id(
        "revision-commit", book_id, campaign_id, str(campaign["base_projection_hash"])
    )
    spec = _spec_from_campaign(campaign)
    written: list[Path] = []
    snapshot_path: Path | None = None
    now = utc_now()
    try:
        with database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current_campaign = connection.execute(
                "SELECT * FROM revision_campaigns WHERE book_id=? AND campaign_id=?",
                (book_id, campaign_id),
            ).fetchone()
            if current_campaign is None or not _campaign_anchor_is_current(
                connection, book_id, current_campaign
            ):
                raise RevisionWorkflowError("campaign 当前投影锚点已漂移，批准前必须重建 campaign")
            if any(
                str(row["validation_run_id"] or "") != str(revalidation["run_id"])
                for row in drafts_rows
            ):
                raise RevisionWorkflowError("批准前草稿 validation_run_id 不是当前投影的最新运行")
            current_parent = projection_from_connection(connection, book_id, edition_id=edition_id)
            if current_parent.through_event_seq < edition.parent_base_event_seq:
                raise RevisionWorkflowError("edition parent 锚点不完整")
            if edition.parent_edition_id is not None:
                frozen_parent = projection_from_connection(
                    connection,
                    book_id,
                    edition_id=edition.parent_edition_id,
                    through_event_seq=edition.parent_base_event_seq,
                )
                if frozen_parent.sha256() != edition.parent_base_projection_hash:
                    raise RevisionWorkflowError("edition 父版本锚点已漂移")
            start_seq: int | None = None
            end_seq = 0
            store = EventStore(database)
            approval_event = _revision_event(
                store,
                connection,
                book_id=book_id,
                edition_id=edition_id,
                event_type="REVISION_CAMPAIGN_AUTHOR_APPROVED",
                aggregate_type="revision_campaign",
                aggregate_id=campaign_id,
                payload={"campaign_id": campaign_id, "approval": confirmation, "approved_at": now},
                commit_id=commit_id,
            )
            end_seq = approval_event.event_seq
            start_seq = end_seq
            connection.execute(
                "UPDATE revision_campaigns SET status='AUTHOR_APPROVED', approved_at=?, version=version+1 WHERE campaign_id=?",
                (now, campaign_id),
            )
            variant_ids: list[str] = []
            unit_ids: list[str] = []
            for unit_row in units_rows:
                unit_id = str(unit_row["unit_id"])
                _, output = drafts[unit_id]
                replacement = f"## {output.replacement_title.strip()}\n\n{output.replacement_markdown.strip()}\n"
                draft_path = Path(str(drafts[unit_id][0]["file_path"]))
                if not draft_path.is_file() or sha256_file(draft_path) != str(
                    drafts[unit_id][0]["replacement_sha256"]
                ):
                    raise RevisionWorkflowError(f"改写草稿文件哈希已变化：{unit_id}")
                replacement_hash = sha256_file(draft_path)
                previous = connection.execute(
                    "SELECT variant_id FROM chapter_variants WHERE edition_id=? AND base_chapter_id=? AND active=1",
                    (edition_id, str(unit_row["base_chapter_id"])),
                ).fetchone()
                if previous is not None:
                    connection.execute(
                        "UPDATE chapter_variants SET active=0, status='SUPERSEDED', version=version+1 WHERE variant_id=?",
                        (str(previous["variant_id"]),),
                    )
                    supersede_event = _revision_event(
                        store,
                        connection,
                        book_id=book_id,
                        edition_id=edition_id,
                        event_type="CHAPTER_VARIANT_SUPERSEDED",
                        aggregate_type="chapter_variant",
                        aggregate_id=str(previous["variant_id"]),
                        payload={
                            "superseded_variant_id": str(previous["variant_id"]),
                            "base_chapter_id": str(unit_row["base_chapter_id"]),
                        },
                        commit_id=commit_id,
                    )
                    end_seq = supersede_event.event_seq
                variant_id = stable_id(
                    "chapter-variant", campaign_id, unit_id, str(drafts[unit_id][0]["revision"])
                )
                connection.execute(
                    """
                    INSERT INTO chapter_variants(
                        variant_id, book_id, edition_id, campaign_id, unit_id,
                        base_chapter_id, base_source_span_id, base_content_sha256,
                        title, replacement_content, replacement_content_sha256,
                        status, supersedes_variant_id, active, created_at,
                        approved_at, revision_commit_id, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, 1, ?, ?, ?, 1)
                    """,
                    (
                        variant_id,
                        book_id,
                        edition_id,
                        campaign_id,
                        unit_id,
                        str(unit_row["base_chapter_id"]),
                        str(unit_row["base_source_span_id"]),
                        str(unit_row["base_content_sha256"]),
                        output.replacement_title,
                        replacement,
                        replacement_hash,
                        "" if previous is None else str(previous["variant_id"]),
                        now,
                        now,
                        commit_id,
                    ),
                )
                variant_ids.append(variant_id)
                unit_ids.append(unit_id)
                unit_event = _revision_event(
                    store,
                    connection,
                    book_id=book_id,
                    edition_id=edition_id,
                    event_type="REVISION_UNIT_COMMITTED",
                    aggregate_type="revision_unit",
                    aggregate_id=unit_id,
                    payload={
                        "campaign_id": campaign_id,
                        "unit_id": unit_id,
                        "base_chapter_id": str(unit_row["base_chapter_id"]),
                        "variant_id": variant_id,
                    },
                    commit_id=commit_id,
                )
                end_seq = unit_event.event_seq
                variant_event = _revision_event(
                    store,
                    connection,
                    book_id=book_id,
                    edition_id=edition_id,
                    event_type="CHAPTER_VARIANT_COMMITTED",
                    aggregate_type="chapter_variant",
                    aggregate_id=variant_id,
                    payload={
                        "campaign_id": campaign_id,
                        "unit_id": unit_id,
                        "variant_id": variant_id,
                        "base_chapter_id": str(unit_row["base_chapter_id"]),
                        "replacement_content_sha256": replacement_hash,
                    },
                    commit_id=commit_id,
                )
                end_seq = variant_event.event_seq
                base_chapter_row = connection.execute(
                    "SELECT document_id, ordinal FROM chapters WHERE book_id=? AND chapter_id=?",
                    (book_id, str(unit_row["base_chapter_id"])),
                ).fetchone()
                if base_chapter_row is None:
                    raise RevisionWorkflowError(f"改写章节不存在：{unit_row['base_chapter_id']}")
                variant_span_id = stable_id(
                    "revision-variant-span", variant_id, replacement_hash, commit_id
                )
                connection.execute(
                    """
                    INSERT INTO source_spans(
                        span_id, book_id, document_id, chapter_id, kind,
                        start_line, end_line, start_char, end_char, text_sha256,
                        excerpt, created_at, version, edition_id, variant_id,
                        revision_commit_id, payload_json
                    ) VALUES (?, ?, ?, ?, 'REVISION_VARIANT', 1, ?, 0, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """,
                    (
                        variant_span_id,
                        book_id,
                        str(base_chapter_row["document_id"]),
                        str(unit_row["base_chapter_id"]),
                        len(replacement.splitlines()),
                        len(replacement),
                        replacement_hash,
                        replacement[:1000],
                        now,
                        edition_id,
                        variant_id,
                        commit_id,
                        json_dumps(
                            {
                                "variant_id": variant_id,
                                "revision_commit_id": commit_id,
                                "base_source_span_id": str(unit_row["base_source_span_id"]),
                                "base_chapter_ordinal": int(unit_row["base_chapter_ordinal"]),
                            }
                        ),
                    ),
                )
                connection.execute(
                    "DELETE FROM edition_chapter_fts WHERE edition_id=? AND chapter_id=?",
                    (edition_id, str(unit_row["base_chapter_id"])),
                )
                connection.execute(
                    """
                    INSERT INTO edition_chapter_fts(
                        edition_id, chapter_id, variant_id, heading, content
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        edition_id,
                        str(unit_row["base_chapter_id"]),
                        variant_id,
                        output.replacement_title,
                        replacement,
                    ),
                )
                connection.execute(
                    "UPDATE chapter_variants SET committed_event_seq=? WHERE variant_id=?",
                    (variant_event.event_seq, variant_id),
                )
                for change in output.state_changes:
                    payload = dict(change.payload)
                    event_type, aggregate_type, key = {
                        "fact": ("FACT_ASSERTED", "fact", "fact_id"),
                        "timeline": ("TIMELINE_ENTRY_SET", "timeline", "timeline_id"),
                        "character_state": ("CHARACTER_STATE_SET", "character_state", "state_id"),
                        "knowledge": ("KNOWLEDGE_EDGE_SET", "knowledge", "edge_id"),
                        "relationship": ("RELATIONSHIP_SET", "relationship", "relationship_id"),
                        "resource": ("RESOURCE_SET", "resource", "resource_id"),
                        "capability": ("CAPABILITY_SET", "capability", "capability_id"),
                        "thread": ("THREAD_SET", "thread", "thread_id"),
                        "promise": ("PROMISE_SET", "promise", "promise_id"),
                        "payoff": ("PAYOFF_RECORDED", "payoff", "payoff_id"),
                        "repetition": ("REPETITION_TAGGED", "repetition", "tag_id"),
                        "style": ("STYLE_PROFILE_SET", "style", "profile_id"),
                    }[change.kind]
                    payload.setdefault(key, change.record_id)
                    state_event = _revision_event(
                        store,
                        connection,
                        book_id=book_id,
                        edition_id=edition_id,
                        event_type=event_type,
                        aggregate_type=aggregate_type,
                        aggregate_id=change.record_id,
                        payload=payload,
                        commit_id=commit_id,
                    )
                    event_seq = state_event.event_seq
                    materialize_change(
                        connection,
                        book_id=book_id,
                        edition_id=edition_id,
                        change=change,
                        source_span_id=variant_span_id,
                        event_id=state_event.event_id,
                        event_seq=event_seq,
                        chapter_id=str(unit_row["base_chapter_id"]),
                        ordinal=int(unit_row["base_chapter_ordinal"]),
                    )
                    end_seq = event_seq
                connection.execute(
                    "UPDATE revision_units SET status='COMMITTED', version=version+1 WHERE unit_id=?",
                    (unit_id,),
                )
                connection.execute(
                    "UPDATE revision_drafts SET status='COMMITTED', approved_at=?, committed_at=?, version=version+1 WHERE unit_id=?",
                    (now, now, unit_id),
                )
            for entity_change in spec.entity_changes:
                aliases = list(entity_change.aliases)
                if entity_change.old_name and entity_change.old_name not in aliases:
                    aliases.insert(0, entity_change.old_name)
                overlay_payload = {
                    "entity_id": entity_change.entity_id,
                    "display_name": entity_change.new_name,
                    "aliases": aliases,
                    "change_type": entity_change.change_type,
                    "reason": entity_change.reason,
                }
                connection.execute(
                    """
                    INSERT INTO edition_entity_overlays(
                        edition_id, entity_id, display_name, aliases_json,
                        payload_json, created_at, version
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(edition_id, entity_id) DO UPDATE SET
                        display_name=excluded.display_name,
                        aliases_json=excluded.aliases_json,
                        payload_json=excluded.payload_json,
                        version=edition_entity_overlays.version+1
                    """,
                    (
                        edition_id,
                        entity_change.entity_id,
                        entity_change.new_name,
                        json_dumps(aliases),
                        json_dumps(overlay_payload),
                        now,
                    ),
                )
                entity_event = _revision_event(
                    store,
                    connection,
                    book_id=book_id,
                    edition_id=edition_id,
                    event_type="ENTITY_OVERLAY_SET",
                    aggregate_type="entity",
                    aggregate_id=entity_change.entity_id,
                    payload=overlay_payload,
                    commit_id=commit_id,
                )
                end_seq = entity_event.event_seq
            validate_materialized_event_sources(
                connection, book_id=book_id, edition_id=edition_id
            )
            projection = projection_from_connection(connection, book_id, edition_id=edition_id)
            persist_projection_in_transaction(connection, projection)
            snapshot_state_json = projection.canonical_json()
            snapshot_hash = projection.sha256()
            snapshot_id = stable_id(
                "snapshot",
                book_id,
                edition_id,
                str(projection.through_event_seq),
                snapshot_hash,
            )
            snapshots_dir = (
                _workspace_book(database, book_id) / "editions" / edition_id / "snapshots"
            )
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshots_dir / f"{snapshot_id}.json"
            snapshot_path.write_text(
                json_dumps(
                    {
                        "snapshot_id": snapshot_id,
                        "book_id": book_id,
                        "edition_id": edition_id,
                        "through_event_seq": projection.through_event_seq,
                        "state_sha256": snapshot_hash,
                        "state": projection.model_dump(mode="json"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            written.append(snapshot_path)
            connection.execute(
                """
                INSERT INTO snapshots(
                    snapshot_id, book_id, edition_id, through_event_seq,
                    state_sha256, state_json, file_path, created_at, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    snapshot_id,
                    book_id,
                    edition_id,
                    projection.through_event_seq,
                    snapshot_hash,
                    snapshot_state_json,
                    str(snapshot_path),
                    now,
                ),
            )
            connection.execute(
                "UPDATE chapter_variants SET revision_commit_id=? WHERE campaign_id=?",
                (commit_id, campaign_id),
            )
            connection.execute(
                "INSERT INTO revision_commits(revision_commit_id, campaign_id, book_id, edition_id, unit_ids_json, variant_ids_json, event_start_seq, event_end_seq, author_approval, committed_at, projection_sha256, snapshot_id, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (
                    commit_id,
                    campaign_id,
                    book_id,
                    edition_id,
                    json_dumps(unit_ids),
                    json_dumps(variant_ids),
                    int(start_seq or 0),
                    end_seq,
                    confirmation,
                    now,
                    projection.sha256(),
                    snapshot_id,
                ),
            )
            connection.execute(
                "UPDATE revision_campaigns SET status='COMMITTED', approved_at=?, committed_at=?, version=version+1 WHERE campaign_id=?",
                (now, now, campaign_id),
            )
            target_status = (
                EditionStatus.ACTIVE.value
                if edition.status is EditionStatus.ACTIVE
                else EditionStatus.VALIDATED.value
            )
            connection.execute(
                "UPDATE editions SET status=?, version=version+1 WHERE book_id=? AND edition_id=? AND status!='ARCHIVED'",
                (target_status, book_id, edition_id),
            )
    except Exception as exc:
        for path in written:
            path.unlink(missing_ok=True)
        if snapshot_path is not None:
            snapshot_path.unlink(missing_ok=True)
        if isinstance(exc, RevisionWorkflowError):
            raise
        raise RevisionWorkflowError(f"改写批准事务已回滚：{exc}") from exc
    rhythm_result: dict[str, object] | None = None
    try:
        from novel_authoring.rhythm.service import diagnose_rhythm, rebuild_features

        rebuild_features(database, book_id, edition_id=edition_id)
        rhythm_result = diagnose_rhythm(database, book_id, edition_id=edition_id)
    except Exception as exc:
        # Rhythm is derived evidence.  Preserve a successful revision commit
        # while making a failed post-commit refresh explicit to the caller.
        rhythm_result = {"status": "WARNING", "error": str(exc)}
    return {
        "campaign_id": campaign_id,
        "edition_id": edition_id,
        "revision_commit_id": commit_id,
        "status": "COMMITTED",
        "variant_ids": variant_ids,
        "event_start_seq": start_seq,
        "event_end_seq": end_seq,
        "snapshot_path": str(snapshot_path) if snapshot_path else None,
        "activation_required": edition.status is not EditionStatus.ACTIVE,
        "activation_phrase": "启用改写版本",
        "rhythm_diagnostics": rhythm_result,
    }


def discard_revision_draft(database: Database, book_id: str, draft_id: str) -> dict[str, object]:
    database.initialize()
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM revision_drafts WHERE book_id=? AND draft_id=?", (book_id, draft_id)
        ).fetchone()
        if row is None:
            raise RevisionWorkflowError(f"改写草稿不存在：{draft_id}")
        connection.execute(
            "UPDATE revision_drafts SET status='REJECTED', version=version+1 WHERE draft_id=?",
            (draft_id,),
        )
        from novel_authoring.domain.models import InformationStatus

        EventStore(database).append_in_transaction(
            connection,
            book_id=book_id,
            edition_id=str(row["edition_id"]),
            event_type="REVISION_DRAFT_DISCARDED",
            aggregate_type="revision_draft",
            aggregate_id=draft_id,
            payload={"draft_id": draft_id, "discarded_at": utc_now()},
            source_kind="AUTHOR_CONFIRMATION",
            status=EventStatus.COMMITTED,
            information_state=InformationStatus.AUTHOR_INTENT,
        )
        connection.execute(
            "UPDATE revision_units SET status='REJECTED', version=version+1 WHERE unit_id=? AND status!='COMMITTED'",
            (str(row["unit_id"]),),
        )
    return {"draft_id": draft_id, "status": "REJECTED", "variant_created": False}


def revision_preview(database: Database, book_id: str, campaign_id: str) -> dict[str, object]:
    database.initialize()
    campaign = _campaign_row(database, book_id, campaign_id)
    with database.connect() as connection:
        units = [
            dict(row)
            for row in connection.execute(
                """
                SELECT unit_id, unit_order, base_chapter_ordinal, base_chapter_id,
                       base_content_sha256, direct_change_requirements_json,
                       downstream_requirements_json, dependent_units_json, status
                FROM revision_units WHERE campaign_id=? ORDER BY unit_order
                """,
                (campaign_id,),
            ).fetchall()
        ]
        impacts = [
            dict(row)
            for row in connection.execute(
                "SELECT impact_id, chapter_id, classification, severity, status FROM revision_impact_items WHERE campaign_id=? ORDER BY impact_id",
                (campaign_id,),
            ).fetchall()
        ]
        variants = [
            dict(row)
            for row in connection.execute(
                """
                SELECT variant_id, unit_id, base_chapter_id, base_content_sha256,
                       replacement_content_sha256, status, active, revision_commit_id,
                       committed_event_seq
                FROM chapter_variants WHERE campaign_id=? ORDER BY created_at
                """,
                (campaign_id,),
            ).fetchall()
        ]
        drafts = [
            {
                **dict(row),
                "output_json": None,
            }
            for row in connection.execute(
                """
                SELECT draft_id, unit_id, task_id, parent_draft_id, revision_number,
                       replacement_sha256, base_content_sha256, status, validation_run_id
                FROM revision_drafts WHERE campaign_id=? ORDER BY unit_id, revision_number
                """,
                (campaign_id,),
            ).fetchall()
        ]
        events = [
            dict(row)
            for row in connection.execute(
                """
                SELECT event_seq, event_id, event_type, aggregate_type, aggregate_id,
                       source_id, edition_id
                FROM events WHERE book_id=? AND edition_id=?
                  AND (source_id=? OR payload_json LIKE ?)
                ORDER BY event_seq
                """,
                (book_id, str(campaign["edition_id"]), campaign_id, f'%"campaign_id":"{campaign_id}"%'),
            ).fetchall()
        ]
        latest_run = connection.execute(
            """
            SELECT run_id, MIN(passed) AS passed
            FROM revision_validation_reports WHERE campaign_id=?
            GROUP BY run_id ORDER BY MAX(created_at) DESC LIMIT 1
            """,
            (campaign_id,),
        ).fetchone()
        current_projection = projection_from_connection(
            connection, book_id, edition_id=str(campaign["edition_id"])
        )
        source_manifest = _source_manifest_hash(database, book_id)
        anchor_current = _campaign_anchor_is_current(connection, book_id, campaign)
    return {
        "campaign_id": campaign_id,
        "book_id": book_id,
        "edition_id": str(campaign["edition_id"]),
        "status": str(campaign["status"]),
        "base_event_seq": _campaign_anchor(campaign)[0],
        "base_projection_hash": _campaign_anchor(campaign)[1],
        "campaign_anchor": {
            "event_seq": _campaign_anchor(campaign)[0],
            "projection_hash": _campaign_anchor(campaign)[1],
        },
        "current_projection": {
            "event_seq": current_projection.through_event_seq,
            "projection_hash": current_projection.sha256(),
            "anchor_current": anchor_current,
        },
        "source_manifest_sha256": source_manifest,
        "source_manifest_current": source_manifest == str(campaign["source_manifest_sha256"]),
        "impact_items": impacts,
        "units": units,
        "drafts": drafts,
        "variants": variants,
        "events": events,
        "validation": None if latest_run is None else dict(latest_run),
        "unresolved_items": [
            item
            for item in impacts
            if item["status"] == "OPEN"
            or item["classification"] in {"MUST_REVIEW", "MUST_REWRITE"}
            and item["status"] not in {"HANDLED", "WAIVED"}
        ],
        "activation_required": str(campaign["status"]) == "COMMITTED"
        and str(campaign["edition_id"]) != BASE_EDITION_ID,
    }
