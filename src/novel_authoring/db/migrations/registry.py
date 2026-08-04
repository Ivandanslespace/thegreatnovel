"""Migration registry facade preserving the historical schema contract."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from novel_authoring.db.schema import MIGRATIONS, SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class MigrationDefinition:
    version: int
    sql: str


def migration_definitions() -> tuple[MigrationDefinition, ...]:
    return tuple(MigrationDefinition(version, sql) for version, sql in MIGRATIONS)


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


__all__ = [
    "MigrationDefinition",
    "SCHEMA_VERSION",
    "applied_versions",
    "migration_definitions",
    "pending_versions",
]
