from __future__ import annotations

import json
from pathlib import Path
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
        result: list[dict[str, Any]] = []
        for row in connection.execute(sql, tuple(params)).fetchall():
            item = dict(row)
            waiting_path = item.get("waiting_for_user_path")
            item["waiting_for_user"] = None
            if waiting_path:
                path = Path(str(waiting_path))
                if path.is_file():
                    try:
                        item["waiting_for_user"] = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        item["waiting_for_user"] = {"path": str(path), "invalid": True}
            result.append(item)
        return result
