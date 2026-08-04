from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any

from novel_authoring.db.database import Database


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf(request: Any, token: str | None) -> None:
    expected = str(request.app.state.csrf_token)
    supplied = token or request.headers.get("X-CSRF-Token")
    if not supplied or not secrets.compare_digest(str(supplied), expected):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=403, detail={"code": "CSRF_INVALID", "message": "CSRF token 无效"}
        )


def database_for_workspace(workspace: Path, book_id: str) -> Database:
    from novel_authoring.utils import safe_book_id

    normalized = safe_book_id(book_id)
    return Database(workspace.resolve() / normalized / "state.sqlite3")
