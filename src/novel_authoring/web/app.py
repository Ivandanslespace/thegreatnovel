from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:  # Optional dependency: CLI/core remains usable without the web extra.
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:  # pragma: no cover - exercised only without optional web deps
    FastAPI = None
    HTTPException = Exception
    Request = Any
    HTMLResponse = JSONResponse = Any
    StaticFiles = None

from novel_authoring.db.database import Database
from novel_authoring.metrics.service import MetricConflictError, MetricValidationError
from novel_authoring.web.dependencies import create_csrf_token, verify_csrf
from novel_authoring.web.routes.jobs import list_handoffs
from novel_authoring.web.routes.metrics import save_author_input
from novel_authoring.web.routes.pages import chapter_context, home_context
from novel_authoring.web.routes.workflow import prepare_continuation, prepare_revision
from novel_authoring.web.schemas import AuthorInputRequest, HandoffRequest, RetractRequest
from novel_authoring.workflows.handoffs import (
    HandoffWorkflowError,
    cancel_handoff,
    copy_instruction,
    get_handoff,
    mark_stale,
)

_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def _check_id(value: str) -> str:
    if not _ID.fullmatch(value):
        raise HTTPException(
            status_code=400, detail={"code": "INVALID_ID", "message": "标识符格式无效"}
        )
    return value


def _error(exc: Exception) -> JSONResponse:
    code = "CONFLICT" if getattr(exc, "status_code", 500) == 409 else "WORKFLOW_ERROR"
    status = 409 if code == "CONFLICT" else 400
    return JSONResponse(
        status_code=status, content={"error": {"code": code, "message": str(exc), "details": {}}}
    )


def create_app(database: Database, *, book_id: str | None = None) -> Any:
    if FastAPI is None:
        raise RuntimeError("Web 功能需要安装可选依赖：pip install -e '.[web]'")
    app = FastAPI(title="Metric Observatory & Author Workbench", docs_url="/api/docs")
    app.state.database = database
    app.state.book_id = book_id
    app.state.csrf_token = create_csrf_token()

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
    async def home() -> HTMLResponse:
        if app.state.book_id is None:
            return HTMLResponse(
                "<h1>Metric Observatory</h1><p>请通过 --book-id 指定本地 book。</p>"
            )
        context = home_context(database, _check_id(str(app.state.book_id)))
        rows = "".join(
            f"<li><a href='/books/{context['book_id']}/editions/"
            f"{context['edition_id']}/chapters/{item['chapter_id']}'>"
            f"{item['ordinal']} {item['title']}</a></li>"
            for item in context["chapters"]
        )
        return HTMLResponse(
            f"<h1>Metric Observatory</h1><p>edition: {context['edition_id']}</p><ul>{rows}</ul>"
        )

    @app.get(
        "/books/{path_book_id}/editions/{edition_id}/chapters/{chapter_id}",
        response_class=HTMLResponse,
    )
    async def chapter_page(path_book_id: str, edition_id: str, chapter_id: str) -> HTMLResponse:
        context = chapter_context(
            database, _check_id(path_book_id), _check_id(edition_id), _check_id(chapter_id)
        )
        return HTMLResponse(
            "<h1>章节审核</h1>"
            f"<h2>{context['chapter']['title']}</h2>"
            f"<pre>{context['chapter']['content']}</pre>"
            f"<script>window.metricBundle={context['bundle']!r}</script>"
        )

    @app.get("/books/{path_book_id}/editions/{edition_id}/missing", response_class=HTMLResponse)
    async def missing_page(path_book_id: str, edition_id: str) -> HTMLResponse:
        book = _check_id(path_book_id)
        edition = _check_id(edition_id)
        context = home_context(database, book)
        chapter = context["chapters"][-1] if context["chapters"] else None
        if chapter is None:
            return HTMLResponse("<h1>缺失输入</h1><p>没有章节。</p>")
        from novel_authoring.metrics.service import MetricsAssembler

        run = MetricsAssembler(database).rebuild(
            book, edition_id=edition, scope_type="CHAPTER", scope_id=str(chapter["chapter_id"])
        )
        rows = "".join(
            f"<li>{item['metric_id']}: {', '.join(item['missing_components'])}</li>"
            for item in run["results"]
            if item["missing_components"]
        )
        return HTMLResponse(f"<h1>缺失输入</h1><p>run_id: {run['run_id']}</p><ul>{rows}</ul>")

    @app.get("/books/{path_book_id}/workflow", response_class=HTMLResponse)
    async def workflow_page(path_book_id: str) -> HTMLResponse:
        return HTMLResponse(
            f"<h1>Workflow Handoff</h1><p>book_id: {_check_id(path_book_id)}</p>"
            "<p>准备续写或改写任务后，在 Windows Codex 桌面端手动复制指令。</p>"
        )

    @app.get("/books/{path_book_id}/jobs", response_class=HTMLResponse)
    async def jobs_page(path_book_id: str) -> HTMLResponse:
        jobs = list_handoffs(database, _check_id(path_book_id))
        rows = "".join(f"<li>{item['handoff_id']}: {item['status']}</li>" for item in jobs)
        return HTMLResponse(f"<h1>Handoff 状态</h1><ul>{rows}</ul>")

    @app.get(
        "/books/{path_book_id}/editions/{edition_id}/draft-review", response_class=HTMLResponse
    )
    async def draft_review_page(path_book_id: str, edition_id: str) -> HTMLResponse:
        database.initialize()
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT draft_id, contract_id, status, file_path FROM drafts "
                "WHERE book_id=? AND edition_id=? ORDER BY created_at DESC",
                (_check_id(path_book_id), _check_id(edition_id)),
            ).fetchall()
        items = "".join(
            f"<li>{row['draft_id']} {row['status']} (contract={row['contract_id']})</li>"
            for row in rows
        )
        return HTMLResponse(f"<h1>Draft Review</h1><ul>{items}</ul><p>本页面不批准草稿。</p>")

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/chapters/{chapter_id}/metrics")
    async def metrics_api(path_book_id: str, edition_id: str, chapter_id: str) -> dict[str, Any]:
        return chapter_context(
            database, _check_id(path_book_id), _check_id(edition_id), _check_id(chapter_id)
        )

    @app.get("/api/books/{path_book_id}/editions/{edition_id}/metrics/missing")
    async def missing_api(path_book_id: str, edition_id: str, scope_id: str) -> dict[str, Any]:
        from novel_authoring.metrics.service import MetricsAssembler

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
                observation_id,
                book_id=_check_id(path_book_id),
                edition_id=_check_id(edition_id),
                scope_type=payload.scope_type,
                scope_id=_check_id(payload.scope_id),
            )
        except (MetricConflictError, MetricValidationError, ValueError) as exc:
            return _error(exc)

    @app.get("/api/handoffs/{handoff_id}")
    async def handoff_api(handoff_id: str) -> dict[str, Any]:
        return get_handoff(database, _check_id(handoff_id))

    @app.get("/api/handoffs/{handoff_id}/instruction")
    async def handoff_instruction_api(handoff_id: str) -> dict[str, str]:
        return {
            "handoff_id": handoff_id,
            "instruction": copy_instruction(database, _check_id(handoff_id)),
        }

    @app.get("/api/books/{path_book_id}/handoffs")
    async def handoffs_api(
        path_book_id: str, edition_id: str | None = None
    ) -> list[dict[str, Any]]:
        return list_handoffs(database, _check_id(path_book_id), edition_id)

    @app.post("/api/books/{path_book_id}/handoffs/continuation")
    async def continuation_api(path_book_id: str, request: Request, payload: HandoffRequest) -> Any:
        verify_csrf(request, None)
        try:
            return prepare_continuation(database, _check_id(path_book_id), payload)
        except (HandoffWorkflowError, ValueError) as exc:
            return _error(exc)

    @app.post("/api/books/{path_book_id}/handoffs/revision")
    async def revision_api(path_book_id: str, request: Request, payload: HandoffRequest) -> Any:
        verify_csrf(request, None)
        try:
            return prepare_revision(database, _check_id(path_book_id), payload)
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
    async def stale_api(handoff_id: str, request: Request) -> Any:
        verify_csrf(request, None)
        try:
            return mark_stale(database, _check_id(handoff_id))
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
