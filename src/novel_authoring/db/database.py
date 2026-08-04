from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from novel_authoring.db.schema import (
    MIGRATIONS,
    SCHEMA_SQL,
    ensure_edition_integrity_schema,
    ensure_rhythm_schema,
    ensure_workbench_schema,
)
from novel_authoring.utils import utc_now


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA_SQL)
            version_one = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = 1"
            ).fetchone()
            if version_one is None:
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, utc_now()),
                )
            for version, sql in MIGRATIONS:
                applied = connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
                ).fetchone()
                if applied is None:
                    connection.executescript(sql)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (version, utc_now()),
                    )
            # Phase-A integrity upgrade remains idempotent for databases created
            # before composite edition keys were enforced.
            ensure_edition_integrity_schema(connection)
            # Legacy promise columns are additive; all new Phase-B/C storage is
            # installed by the formal Migration 6 above.
            ensure_rhythm_schema(connection)
            # Keep early v7 databases compatible with the final handoff schema
            # without changing the recorded migration history.
            ensure_workbench_schema(connection)
            # 迁移只负责结构；每次初始化再幂等回填已有 book 的 base edition。
            # 使用局部导入避免 db -> edition -> projection -> db 的导入环。
            from novel_authoring.edition import backfill_base_editions

            backfill_base_editions(connection)

    def scalar(self, sql: str, parameters: tuple[object, ...] = ()) -> object | None:
        with self.connect() as connection:
            row = connection.execute(sql, parameters).fetchone()
            return None if row is None else row[0]
