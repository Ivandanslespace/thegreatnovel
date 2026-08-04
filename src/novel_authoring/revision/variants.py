"""chapter variant 提交 API 的公开门面。"""

from novel_authoring.revision.service import (  # noqa: F401
    approve_revision_campaign,
    discard_revision_draft,
    revision_preview,
)
