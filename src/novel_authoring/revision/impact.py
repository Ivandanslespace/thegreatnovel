"""影响分析 API 的公开门面。"""

from novel_authoring.revision.service import (  # noqa: F401
    build_revision_impact,
    complete_revision_impact_audit,
    confirm_revision_impact_audit,
)
