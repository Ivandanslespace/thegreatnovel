"""版本化、显式批准的小说改写工作流。"""

from novel_authoring.revision.models import (
    ChangeMapItem,
    ImpactItem,
    ImpactPacket,
    RevisionDraftOutput,
    RevisionSpec,
    RevisionUnit,
)
from novel_authoring.revision.service import (
    REVISION_APPROVAL_PHRASE,
    RevisionWorkflowError,
    approve_revision_campaign,
    build_revision_impact,
    build_revision_plan,
    complete_revision_impact_audit,
    create_revision_campaign,
    discard_revision_draft,
    import_revision_draft,
    list_revision_campaigns,
    prepare_revision_draft_task,
    revision_preview,
    validate_revision_campaign,
)

__all__ = [
    "ChangeMapItem",
    "ImpactItem",
    "ImpactPacket",
    "RevisionDraftOutput",
    "RevisionSpec",
    "RevisionUnit",
    "RevisionWorkflowError",
    "REVISION_APPROVAL_PHRASE",
    "approve_revision_campaign",
    "build_revision_impact",
    "build_revision_plan",
    "complete_revision_impact_audit",
    "create_revision_campaign",
    "discard_revision_draft",
    "import_revision_draft",
    "list_revision_campaigns",
    "prepare_revision_draft_task",
    "revision_preview",
    "validate_revision_campaign",
]
