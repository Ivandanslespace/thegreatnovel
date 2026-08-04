from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

try:  # Optional dependency: CLI/core remains usable without the web extra.
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ImportError:  # pragma: no cover - exercised only without web extras
    FastAPI = None  # type: ignore[misc, assignment]
    HTTPException = Exception  # type: ignore[misc, assignment]
    Request = Any  # type: ignore[misc, assignment]
    HTMLResponse = JSONResponse = Any  # type: ignore[misc, assignment]
    StaticFiles = None  # type: ignore[misc, assignment]
    Jinja2Templates = None  # type: ignore[misc, assignment]

from novel_authoring.db.database import Database
from novel_authoring.edition import edition_chapters, list_editions
from novel_authoring.metrics.registry import load_registry
from novel_authoring.metrics.segments import list_segments
from novel_authoring.metrics.service import (
    MetricConflictError,
    MetricsAssembler,
    MetricValidationError,
    ObservationResolver,
)
from novel_authoring.web.dependencies import create_csrf_token, verify_csrf
from novel_authoring.web.routes.jobs import list_handoffs
from novel_authoring.web.routes.metrics import save_author_input
from novel_authoring.web.routes.pages import (
    chapter_context,
    dashboard_context,
    home_context,
    metric_history,
    observation_history,
    workflow_context,
)
from novel_authoring.web.routes.workflow import prepare_continuation, prepare_revision
from novel_authoring.web.schemas import (
    AuthorInputRequest,
    HandoffRequest,
    RecomputeRequest,
    RetractRequest,
    UserResponseRequest,
)
from novel_authoring.workflows.handoffs import (
    HandoffWorkflowError,
    cancel_handoff,
    copy_instruction,
    get_handoff,
    mark_stale,
    record_user_response,
    validate_result_file,
)

_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _check_id(value: str) -> str:
    if not _ID.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_ID", "message": "标识符格式无效", "details": {}},
        )
    return value


def _error(exc: Exception) -> JSONResponse:
    code = "CONFLICT" if getattr(exc, "status_code", 500) == 409 else "WORKFLOW_ERROR"
    status = 409 if code == "CONFLICT" else 400
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": str(exc), "details": {}}},
    )


def _template(templates: Any, name: str, request: Request, context: dict[str, Any]) -> Any:
    context = {"request": request, **context}
    return templates.TemplateResponse(request=request, name=name, context=context)


def create_app(database: Database, *, book_id: str | None = None) -> Any:
    if FastAPI is None or Jinja2Templates is None:
        raise RuntimeError("Web 功能需要安装可选依赖：pip install '.[web]'")
    app = FastAPI(title="Author Workbench", docs_url="/api/docs")
    app.state.database = database
    app.state.book_id = book_id
    app.state.csrf_token = create_csrf_token()
    template_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=str(template_dir))
    templates.env.autoescape = True

    @app.exception_handler(HTTPException)
    async def handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        if "code" not in detail:
            detail = {"code": "HTTP_ERROR", **detail}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {**detail, "details": detail.get("details", {})}},
        )

    @app.exception_handler(Exception)
    async def handle_error(_request: Request, exc: Exception) -> JSONResponse:
        return _error(exc)

    if StaticFiles is not None:
        app.mount(
            "/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "executor": "Windows Codex desktop client via local file handoff"}

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> Any:
        if app.state.book_id is None:
            return _template(
                templates,
                "missing.html",
                request,
                {"run": {"run_id": "", "results": []}, "csrf_token": app.state.csrf_token},
            )
        context = dashboard_context(database, _check_id(str(app.state.book_id)))
        context["csrf_token"] = app.state.csrf_token
        return _template(templates, "index.html", request, context)

    @app.get(
        "/books/{path_book_id}/editions/{edition_id}/chapters/{chapter_id}",
        response_class=HTMLResponse,
    )
    async def chapter_page(
        request: Request, path_book_id: str, edition_id: str, chapter_id: str
    ) -> Any:
        try:
            context = chapter_context(
                database, _check_id(path_book_id), _check_id(edition_id), _check_id(chapter_id)
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(exc), "details": {}},
            ) from exc
        context["csrf_token"] = app.state.csrf_token
        return _template(templates, "chapter.html", request, context)

    @app.get("/books/{path_book_id}/editions/{edition_id}/missing", response_class=HTMLResponse)
    async def missing_page(request: Request, path_book_id: str, edition_id: str) -> Any:
        book = _check_id(path_book_id)
        edition = _check_id(edition_id)
        database.initialize()
        with database.connect() as connection:
            edition_rows = edition_chapters(connection, book, edition)
        chapter = edition_rows[-1] if edition_rows else None
        if chapter is None:
            return _template(
                templates,
                "missing.html",
                request,
                {"run": {"run_id": "", "results": []}, "csrf_token": app.state.csrf_token},
            )
        run = MetricsAssembler(database).rebuild(
            book, edition_id=edition, scope_type="CHAPTER", scope_id=str(chapter["chapter_id"])
        )
        segments = list_segments(
            database,
            book,
            edition_id=edition,
            chapter_id=str(chapter["chapter_id"]),
        )
        registry = load_registry()
        component_definitions: dict[str, dict[str, Any]] = {}
        for metric in run["results"]:
            definition = registry.metric(str(metric["metric_id"]))
            component_definitions[str(metric["metric_id"])] = {
                component_id: {
                    "display_name": component.display_name,
                    "description": component.description,
                    "minimum": component.minimum,
                    "maximum": component.maximum,
                    "value_type": component.value_type,
                    "evidence_required": component.evidence_required,
                    "allowed_source_kinds": [item.value for item in component.allowed_source_kinds],
                }
                for component_id, component in definition.components.items()
            }
        return _template(
            templates,
            "missing.html",
            request,
            {
                "run": run,
                "book_id": book,
                "edition_id": edition,
                "scope_id": str(chapter["chapter_id"]),
                "chapter": chapter,
                "segments": segments,
                "component_definitions": component_definitions,
                "csrf_token": app.state.csrf_token,
            },
        )

    @app.get("/books/{path_book_id}/workflow", response_class=HTMLResponse)
    async def workflow_page(request: Request, path_book_id: str) -> Any:
        context = workflow_context(database, _check_id(path_book_id))
        context["edition_id"] = home_context(database, _check_id(path_book_id))["edition_id"]
        context["csrf_token"] = app.state.csrf_token
        return _template(templates, "workflow.html", request, context)

    @app.get("/books/{path_book_id}/jobs", response_class=HTMLResponse)
    async def jobs_page(request: Request, path_book_id: str) -> Any:
        checked = _check_id(path_book_id)
        context = {"book_id": checked, "handoffs": list_handoffs(database, checked)}
        context["csrf_token"] = app.state.csrf_token
        return _template(templates, "jobs.html", request, context)

    @app.get(
        "/books/{path_book_id}/editions/{edition_id}/draft-review", response_class=HTMLResponse
    )
    async def draft_review_page(request: Request, path_book_id: str, edition_id: str) -> Any:
        database.initialize()
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM drafts "
                "WHERE book_id=? AND edition_id=? ORDER BY created_at DESC",
                (_check_id(path_book_id), _check_id(edition_id)),
            ).fetchall()
            drafts: list[dict[str, Any]] = []
            for row in rows:
                draft = dict(row)
                draft["display_status"] = (
                    "VALIDATED_DRAFT"
                    if str(draft["status"]) == "VALIDATED"
                    else str(draft["status"])
                )
                draft_path = Path(str(draft.get("file_path") or ""))
                try:
                    draft["content"] = (
                        draft_path.read_text(encoding="utf-8")[:200_000]
                        if draft_path.is_file()
                        else ""
                    )
                except OSError:
                    draft["content"] = ""
                try:
                    draft["output"] = json.loads(str(draft.get("output_json") or "{}"))
                except ValueError:
                    draft["output"] = {"raw": draft.get("output_json", "")}
                reports = connection.execute(
                    "SELECT validator, severity, passed, report_json, run_id "
                    "FROM validation_reports WHERE draft_id=? ORDER BY validator, created_at",
                    (str(row["draft_id"]),),
                ).fetchall()
                draft["validation_reports"] = []
                for report in reports:
                    item = dict(report)
                    try:
                        item["report"] = json.loads(str(item.get("report_json") or "{}"))
                    except ValueError:
                        item["report"] = {"raw": item.get("report_json", "")}
                    draft["validation_reports"].append(item)
                draft["candidates"] = [
                    dict(candidate)
                    for candidate in connection.execute(
                        "SELECT candidate_id, rank, primary_thread_id, primary_function, "
                        "selection_status, status FROM candidate_plans "
                        "WHERE book_id=? AND edition_id=? ORDER BY rank, created_at",
                        (_check_id(path_book_id), _check_id(edition_id)),
                    ).fetchall()
                ]
                contract = connection.execute(
                    "SELECT * FROM chapter_contracts WHERE contract_id=?",
                    (str(row["contract_id"]),),
                ).fetchone()
                draft["contract"] = None if contract is None else dict(contract)
                rhythm = connection.execute(
                    "SELECT snapshot_json FROM rhythm_diagnostic_snapshots "
                    "WHERE book_id=? AND edition_id=? ORDER BY as_of_chapter DESC, "
                    "created_at DESC LIMIT 1",
                    (_check_id(path_book_id), _check_id(edition_id)),
                ).fetchone()
                try:
                    draft["rhythm"] = {} if rhythm is None else json.loads(
                        str(rhythm["snapshot_json"] or "{}")
                    )
                except ValueError:
                    draft["rhythm"] = {"raw": rhythm["snapshot_json"]}
                draft["promises"] = [
                    dict(promise)
                    for promise in connection.execute(
                        "SELECT promise_id, statement, status, progress, target_max_age "
                        "FROM promises WHERE book_id=? AND edition_id=? ORDER BY importance DESC",
                        (_check_id(path_book_id), _check_id(edition_id)),
                    ).fetchall()
                ]
                draft["metric_changes"] = draft["output"].get("metric_changes", [])
                draft["state_changes"] = draft["output"].get("state_changes", [])
                draft["approval_preview"] = {
                    "draft_id": draft["draft_id"],
                    "current_status": draft["status"],
                    "canon_commit": False,
                    "author_confirmation_required": True,
                    "continuation_approval_command": (
                        f"novel approve --book-id {_check_id(path_book_id)} "
                        f"--draft-id {draft['draft_id']} --confirm '批准写入正史'"
                    ),
                    "revision_approval_command": "novel revision approve --confirm '批准改写版本'",
                    "note": "此预览不会写入 Canon；批准必须由作者在 CLI 明确执行。",
                }
                drafts.append(draft)
        return _template(
            templates,
            "draft_review.html",
            request,
            {"drafts": drafts, "csrf_token": app.state.csrf_token},
        )

    @app.get("/api/books")
    async def books_api() -> list[dict[str, Any]]:
        database.initialize()
        with database.connect() as connection:
            rows = connection.execute("SELECT * FROM books ORDER BY title, book_id").fetchall()
            return [dict(row) for row in rows]

    @app.get("/api/books/{path_book_id}/editions")
    async def editions_api(path_book_id: str) -> list[dict[str, Any]]:
        return [
            item.model_dump(mode="json")
            for item in list_editions(database, _check_id(path_book_id))
        ]

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/chapters")
    async def chapters_api(path_book_id: str, edition_id: str) -> list[dict[str, Any]]:
        database.initialize()
        with database.connect() as connection:
            return edition_chapters(
                connection, _check_id(path_book_id), _check_id(edition_id)
            )

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/chapters/{chapter_id}")
    async def chapter_detail_api(
        path_book_id: str, edition_id: str, chapter_id: str
    ) -> dict[str, Any]:
        try:
            return chapter_context(
                database, _check_id(path_book_id), _check_id(edition_id), _check_id(chapter_id)
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(exc), "details": {}},
            ) from exc

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/chapters/{chapter_id}/segments")
    async def segments_api(
        path_book_id: str, edition_id: str, chapter_id: str
    ) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]],
            chapter_context(
                database, _check_id(path_book_id), _check_id(edition_id), _check_id(chapter_id)
            )["segments"],
        )

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/chapters/{chapter_id}/metrics")
    async def metrics_api(path_book_id: str, edition_id: str, chapter_id: str) -> dict[str, Any]:
        return chapter_context(
            database, _check_id(path_book_id), _check_id(edition_id), _check_id(chapter_id)
        )

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/metric-history")
    async def metric_history_api(
        path_book_id: str, edition_id: str, scope_type: str = "CHAPTER", scope_id: str = ""
    ) -> list[dict[str, Any]]:
        if not scope_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "MISSING_SCOPE_ID", "message": "需要 scope_id"},
            )
        return metric_history(
            database,
            _check_id(path_book_id),
            _check_id(edition_id),
            scope_type,
            _check_id(scope_id),
        )

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/metrics/observations/history")
    async def observation_history_api(
        path_book_id: str,
        edition_id: str,
        scope_type: str = "CHAPTER",
        scope_id: str = "",
    ) -> list[dict[str, Any]]:
        if not scope_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "MISSING_SCOPE_ID", "message": "需要 scope_id"},
            )
        return observation_history(
            database,
            _check_id(path_book_id),
            _check_id(edition_id),
            scope_type,
            _check_id(scope_id),
        )

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/metrics/missing")
    @app.get("/api/books/{path_book_id}/editions/{edition_id}/missing-inputs")
    async def missing_api(path_book_id: str, edition_id: str, scope_id: str) -> dict[str, Any]:
        run = MetricsAssembler(database).rebuild(
            _check_id(path_book_id),
            edition_id=_check_id(edition_id),
            scope_type="CHAPTER",
            scope_id=_check_id(scope_id),
        )
        return {
            "run_id": run["run_id"],
            "missing": {
                item["metric_id"]: item["missing_components"]
                for item in run["results"]
                if item["missing_components"]
            },
        }

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/disputes")
    async def disputes_api(
        path_book_id: str, edition_id: str, scope_id: str
    ) -> list[dict[str, Any]]:
        database.initialize()
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT scope_type, metric_id, component_id "
                "FROM metric_observations WHERE book_id=? AND edition_id=? AND scope_id=? "
                "ORDER BY metric_id, component_id",
                (_check_id(path_book_id), _check_id(edition_id), _check_id(scope_id)),
            ).fetchall()
        resolver = ObservationResolver(database)
        disputes: list[dict[str, Any]] = []
        for row in rows:
            resolution = resolver.resolve(
                _check_id(path_book_id),
                _check_id(edition_id),
                str(row["scope_type"]),
                _check_id(scope_id),
                str(row["metric_id"]),
                str(row["component_id"]),
            )
            if resolution.status.value == "DISPUTED":
                disputes.append(
                    {
                        "scope_type": str(row["scope_type"]),
                        "metric_id": str(row["metric_id"]),
                        "component_id": str(row["component_id"]),
                        "resolution": resolution.model_dump(mode="json"),
                    }
                )
        return disputes

    @app.post("/api/books/{path_book_id}/editions/{edition_id}/metrics/observations")
    async def author_input_api(
        path_book_id: str, edition_id: str, request: Request, payload: AuthorInputRequest
    ) -> Any:
        verify_csrf(request, None)
        try:
            return save_author_input(
                database, _check_id(path_book_id), _check_id(edition_id), payload
            )
        except (MetricConflictError, MetricValidationError, ValueError) as exc:
            return _error(exc)

    @app.post(
        "/api/books/{path_book_id}/editions/{edition_id}/metrics/observations/"
        "{observation_id}/retract"
    )
    async def retract_observation_api(
        path_book_id: str,
        edition_id: str,
        observation_id: str,
        request: Request,
        payload: RetractRequest,
    ) -> Any:
        verify_csrf(request, None)
        try:
            from novel_authoring.metrics.service import AuthorMetricInputService

            return AuthorMetricInputService(database).retract(
                _check_id(observation_id),
                book_id=_check_id(path_book_id),
                edition_id=_check_id(edition_id),
                scope_type=payload.scope_type,
                scope_id=_check_id(payload.scope_id),
                reason=payload.reason,
                expected_active_observation_id=payload.expected_active_observation_id,
            )
        except (MetricConflictError, MetricValidationError, ValueError) as exc:
            return _error(exc)

    @app.post("/api/books/{path_book_id}/editions/{edition_id}/metrics/recompute")
    async def recompute_api(
        path_book_id: str, edition_id: str, request: Request, payload: RecomputeRequest
    ) -> Any:
        verify_csrf(request, None)
        try:
            assembler = MetricsAssembler(database)
            bundle = assembler.assemble(
                _check_id(path_book_id),
                edition_id=_check_id(edition_id),
                scope_type=payload.scope_type,
                scope_id=_check_id(payload.scope_id),
                requested_metric_ids=payload.requested_metric_ids,
            )
            for field, expected in (
                ("effective_content_sha256", bundle.effective_content_sha256),
                ("projection_hash", bundle.projection_hash),
                ("registry_hash", bundle.registry_hash),
                ("config_hash", bundle.config_hash),
            ):
                supplied = getattr(payload, field)
                if supplied is not None and supplied != expected:
                    raise MetricConflictError(f"{field} 已变化，请刷新后重试")
            resolver = ObservationResolver(database)
            for key, expected_id in payload.expected_effective_observation_ids.items():
                parts = key.split(".", 1)
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    raise MetricValidationError(
                        "expected_effective_observation_ids 的 key 必须是 metric_id.component_id"
                    )
                current = resolver.resolve(
                    _check_id(path_book_id),
                    _check_id(edition_id),
                    payload.scope_type,
                    _check_id(payload.scope_id),
                    parts[0],
                    parts[1],
                ).effective_observation_id
                if current != expected_id:
                    raise MetricConflictError(f"{key} 的 active observation 已变化，请刷新后重试")
            return assembler.run(bundle)
        except (MetricConflictError, MetricValidationError, ValueError) as exc:
            return _error(exc)

    @app.get("/api/handoffs")
    async def all_handoffs_api(book: str | None = None) -> list[dict[str, Any]]:
        database.initialize()
        with database.connect() as connection:
            if book is None:
                rows = connection.execute(
                    "SELECT * FROM workflow_handoffs ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM workflow_handoffs WHERE book_id=? ORDER BY created_at DESC",
                    (_check_id(book),),
                ).fetchall()
        return [dict(row) for row in rows]

    @app.get("/api/handoffs/{handoff_id}")
    async def handoff_api(handoff_id: str) -> dict[str, Any]:
        return get_handoff(database, _check_id(handoff_id))

    @app.get("/api/handoffs/{handoff_id}/events")
    async def handoff_events_api(handoff_id: str) -> list[dict[str, Any]]:
        return cast(list[dict[str, Any]], get_handoff(database, _check_id(handoff_id))["events"])

    @app.get("/api/handoffs/{handoff_id}/result")
    async def handoff_result_api(handoff_id: str) -> dict[str, Any]:
        item = get_handoff(database, _check_id(handoff_id))
        if item.get("status") == "COMPLETED":
            item["validated_result"] = validate_result_file(database, handoff_id)
        return {
            key: item[key]
            for key in ("handoff_id", "status", "result", "validated_result")
            if key in item
        }

    @app.get("/api/handoffs/{handoff_id}/instruction")
    async def handoff_instruction_api(handoff_id: str) -> dict[str, str]:
        checked = _check_id(handoff_id)
        return {"handoff_id": checked, "instruction": copy_instruction(database, checked)}

    @app.get("/api/books/{path_book_id}/handoffs")
    async def handoffs_api(
        path_book_id: str, edition_id: str | None = None
    ) -> list[dict[str, Any]]:
        return list_handoffs(database, _check_id(path_book_id), edition_id)

    @app.post("/api/handoffs/continue")
    @app.post("/api/books/{path_book_id}/handoffs/continuation")
    async def continuation_api(
        request: Request, payload: HandoffRequest, path_book_id: str | None = None
    ) -> Any:
        verify_csrf(request, None)
        try:
            target_book = path_book_id or app.state.book_id
            if target_book is None:
                raise HandoffWorkflowError("需要 book_id")
            return prepare_continuation(database, _check_id(str(target_book)), payload)
        except (HandoffWorkflowError, ValueError) as exc:
            return _error(exc)

    @app.post("/api/handoffs/revise")
    @app.post("/api/books/{path_book_id}/handoffs/revision")
    async def revision_api(
        request: Request, payload: HandoffRequest, path_book_id: str | None = None
    ) -> Any:
        verify_csrf(request, None)
        try:
            target_book = path_book_id or app.state.book_id
            if target_book is None:
                raise HandoffWorkflowError("需要 book_id")
            return prepare_revision(database, _check_id(str(target_book)), payload)
        except (HandoffWorkflowError, ValueError) as exc:
            return _error(exc)

    @app.post("/api/handoffs/{handoff_id}/cancel")
    async def cancel_api(handoff_id: str, request: Request) -> Any:
        verify_csrf(request, None)
        try:
            return cancel_handoff(database, _check_id(handoff_id))
        except HandoffWorkflowError as exc:
            return _error(exc)

    @app.post("/api/handoffs/{handoff_id}/stale")
    @app.post("/api/handoffs/{handoff_id}/mark-stale")
    async def stale_api(handoff_id: str, request: Request) -> Any:
        verify_csrf(request, None)
        try:
            return mark_stale(database, _check_id(handoff_id))
        except HandoffWorkflowError as exc:
            return _error(exc)

    @app.post("/api/handoffs/{handoff_id}/user-response")
    async def user_response_api(
        handoff_id: str, request: Request, payload: UserResponseRequest
    ) -> Any:
        verify_csrf(request, None)
        try:
            return record_user_response(database, _check_id(handoff_id), payload.response)
        except HandoffWorkflowError as exc:
            return _error(exc)

    return app


def serve(
    database: Database,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    allow_remote: bool = False,
    book_id: str | None = None,
) -> None:
    if host not in ("127.0.0.1", "localhost", "::1") and not allow_remote:
        raise ValueError("默认只允许本机绑定；需要远程访问时显式传入 allow_remote")
    import uvicorn

    uvicorn.run(create_app(database, book_id=book_id), host=host, port=port)
