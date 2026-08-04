from __future__ import annotations

from typing import Any


def list_handoffs(
    database: Any, book_id: str, edition_id: str | None = None
) -> list[dict[str, Any]]:
    database.initialize()
    with database.connect() as connection:
        sql = "SELECT * FROM workflow_handoffs WHERE book_id=?"
        params: list[object] = [book_id]
        if edition_id:
            sql += " AND edition_id=?"
            params.append(edition_id)
        sql += " ORDER BY created_at DESC"
        return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]
