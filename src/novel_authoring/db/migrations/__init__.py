"""低风险数据库迁移 facade。

历史 SQL 的含义仍由 ``db.schema`` 保持；本包提供稳定的 registry 入口，便于后续按
版本拆分而不改变已有 migration 编号或执行顺序。
"""

from novel_authoring.db.migrations.registry import (
    MigrationDefinition,
    applied_versions,
    migration_definitions,
    pending_versions,
)

__all__ = [
    "MigrationDefinition",
    "applied_versions",
    "migration_definitions",
    "pending_versions",
]
