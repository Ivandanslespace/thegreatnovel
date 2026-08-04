"""Executable registry for versioned database migrations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from novel_authoring.db.schema import SCHEMA_VERSION

from .migration_2 import SQL as MIGRATION_2_SQL
from .migration_3 import SQL as MIGRATION_3_SQL
from .migration_4 import SQL as MIGRATION_4_SQL
from .migration_5 import SQL as MIGRATION_5_SQL
from .migration_6 import SQL as MIGRATION_6_SQL
from .migration_7 import SQL as MIGRATION_7_SQL
from .migration_8 import SQL as MIGRATION_8_SQL


@dataclass(frozen=True, slots=True)
class MigrationDefinition:
    version: int
    sql: str


def migration_definitions() -> tuple[MigrationDefinition, ...]:
    definitions = tuple(
        MigrationDefinition(version, sql)
        for version, sql in (
            (2, MIGRATION_2_SQL),
            (3, MIGRATION_3_SQL),
            (4, MIGRATION_4_SQL),
            (5, MIGRATION_5_SQL),
            (6, MIGRATION_6_SQL),
            (7, MIGRATION_7_SQL),
            (8, MIGRATION_8_SQL),
        )
    )
    expected = tuple(range(2, SCHEMA_VERSION + 1))
    actual = tuple(item.version for item in definitions)
    if actual != expected or len(set(actual)) != len(actual):
        raise RuntimeError(f"migration registry 版本不连续或重复: {actual}")
    return definitions


def applied_versions(connection: sqlite3.Connection) -> tuple[int, ...]:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    if table is None:
        return ()
    return tuple(
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
    )


def pending_versions(connection: sqlite3.Connection) -> tuple[int, ...]:
    applied = set(applied_versions(connection))
    return tuple(
        definition.version
        for definition in migration_definitions()
        if definition.version not in applied
    )


def apply_pending(
    connection: sqlite3.Connection, *, applied_at: str | None = None
) -> tuple[int, ...]:
    """Execute pending definitions in order and record each atomically."""

    applied = set(applied_versions(connection))
    completed: list[int] = []
    for definition in migration_definitions():
        if definition.version in applied:
            continue
        connection.executescript(definition.sql)
        if applied_at is None:
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, datetime('now'))",
                (definition.version,),
            )
        else:
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (definition.version, applied_at),
            )
        completed.append(definition.version)
    return tuple(completed)


__all__ = [
    "MigrationDefinition",
    "SCHEMA_VERSION",
    "apply_pending",
    "applied_versions",
    "migration_definitions",
    "pending_versions",
]
