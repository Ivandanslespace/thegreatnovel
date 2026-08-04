"""Canonical book-library storage primitives.

The storage package owns paths only.  It deliberately does not change Canon,
metric, Atlas, or approval semantics; those services consume the paths exposed
by :class:`BookLayout`.
"""

from novel_authoring.storage.layout import BookLayout, default_library_root
from novel_authoring.storage.migration import (
    MigrationOptions,
    MigrationPlan,
    MigrationResult,
    cleanup_legacy,
    migrate_legacy,
    plan_legacy_cleanup,
    plan_legacy_migration,
)
from novel_authoring.storage.models import (
    BookPaths,
    EditionPaths,
    LayoutError,
    OperationPaths,
)
from novel_authoring.storage.registry import BookRecord, BookRegistry

__all__ = [
    "BookLayout",
    "BookPaths",
    "BookRecord",
    "BookRegistry",
    "MigrationOptions",
    "MigrationPlan",
    "MigrationResult",
    "EditionPaths",
    "LayoutError",
    "OperationPaths",
    "cleanup_legacy",
    "default_library_root",
    "migrate_legacy",
    "plan_legacy_cleanup",
    "plan_legacy_migration",
]
