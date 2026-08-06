from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from novel_authoring.canon.projection import rebuild_projection
from novel_authoring.config import Settings, load_settings
from novel_authoring.context.router import ContextPurpose, route_runtime_context
from novel_authoring.contracts.draft import DraftOutput
from novel_authoring.db.database import Database
from novel_authoring.domain.models import DraftStatus
from novel_authoring.edition import edition_workspace, resolve_edition_id
from novel_authoring.planning.models import ChapterContract
from novel_authoring.storage.layout import BookLayout
from novel_authoring.storage.operations import book_root
from novel_authoring.utils import json_dumps, sha256_file, stable_id, utc_now
from novel_authoring.validation.models import VALIDATOR_NAMES, ValidationBundle
from novel_authoring.validation.validators import VALIDATORS, ValidationContext


class ValidationWorkflowError(RuntimeError):
    pass


def validate_draft(
    database: Database,
    book_id: str,
    draft_id: str,
    settings: Settings | None = None,
    *,
    edition_id: str | None = None,
) -> ValidationBundle:
    database.initialize()
    selected_edition = resolve_edition_id(database, book_id, edition_id)
    with database.connect() as connection:
        row = connection.execute(
            """
            SELECT d.*, c.contract_json
            FROM drafts d JOIN chapter_contracts c ON c.contract_id=d.contract_id
            WHERE d.book_id=? AND d.draft_id=? AND d.edition_id=?
            """,
            (book_id, draft_id, selected_edition),
        ).fetchone()
    if row is None:
        raise ValidationWorkflowError(f"草稿不存在：{draft_id}")
    if row["status"] in {
        DraftStatus.AUTHOR_APPROVED.value,
        DraftStatus.CANON_COMMITTED.value,
        DraftStatus.REJECTED.value,
    }:
        raise ValidationWorkflowError(f"草稿状态不可校验：{row['status']}")
    draft_path = Path(str(row["file_path"]))
    if not draft_path.is_file():
        raise ValidationWorkflowError(f"草稿文件不存在：{draft_path}")
    actual_hash = sha256_file(draft_path)
    expected_hash = str(row["content_sha256"])
    if actual_hash != expected_hash:
        raise ValidationWorkflowError("草稿文件哈希已变化，必须重新导入后再校验")
    try:
        draft = DraftOutput.model_validate_json(str(row["output_json"]))
        contract = ChapterContract.model_validate_json(str(row["contract_json"]))
    except ValidationError as exc:
        raise ValidationWorkflowError(f"持久化合同无效：{exc}") from exc
    projection = rebuild_projection(database, book_id, edition_id=selected_edition, persist=False)
    runtime_context = route_runtime_context(
        database,
        book_id,
        edition_id=selected_edition,
        purpose=ContextPurpose.VALIDATION,
    )
    context = ValidationContext(
        draft=draft,
        contract=contract,
        projection=projection,
        settings=settings or load_settings(),
        runtime_context=runtime_context,
    )
    reports = [validator(context) for validator in VALIDATORS]
    names = tuple(report.validator for report in reports)
    if names != VALIDATOR_NAMES:
        raise ValidationWorkflowError("十项校验器集合或顺序不完整")
    passed = all(report.passed for report in reports)
    created_at = utc_now()
    run_id = stable_id(
        "validation",
        draft_id,
        expected_hash,
        projection.sha256(),
    )
    bundle = ValidationBundle(
        run_id=run_id,
        book_id=book_id,
        draft_id=draft_id,
        contract_id=contract.contract_id,
        content_sha256=expected_hash,
        projection_sha256=projection.sha256(),
        through_event_seq=projection.through_event_seq,
        passed=passed,
        reports=reports,
        created_at=created_at,
    )
    workspace = edition_workspace(database, book_id, selected_edition)
    root = book_root(database, book_id)
    validation_dir = (
        BookLayout(root.parent).for_book(book_id).edition(selected_edition).validation
        if (root / "book.yaml").is_file()
        else workspace / "validation"
    )
    validation_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = validation_dir / f"{draft_id}.json"
    artifact_path.write_text(
        json_dumps(bundle.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    with database.connect() as connection:
        connection.execute(
            "DELETE FROM validation_reports WHERE draft_id=? AND run_id=?",
            (draft_id, run_id),
        )
        for report in reports:
            report_json = json_dumps(report.model_dump(mode="json"))
            report_id = stable_id("validation-report", run_id, report.validator)
            connection.execute(
                """
                INSERT INTO validation_reports(
                report_id, book_id, edition_id, draft_id, validator, severity, passed,
                    report_json, created_at, version, run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    report_id,
                    book_id,
                    selected_edition,
                    draft_id,
                    report.validator,
                    report.severity.value,
                    int(report.passed),
                    report_json,
                    created_at,
                    run_id,
                ),
            )
        connection.execute(
            "UPDATE drafts SET status=?, validation_run_id=? WHERE draft_id=? AND edition_id=?",
            (
                DraftStatus.VALIDATED.value if passed else DraftStatus.DRAFT.value,
                run_id,
                draft_id,
                selected_edition,
            ),
        )
    return bundle
