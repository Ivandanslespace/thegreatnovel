from __future__ import annotations

from typing import Any

from novel_authoring.workflows.handoffs import create_continuation_handoff, create_revision_handoff


def prepare_continuation(database: Any, book_id: str, request: Any) -> dict[str, Any]:
    return create_continuation_handoff(
        database,
        book_id,
        edition_id=request.edition_id,
        requested_stage=request.requested_stage,
        require_complete_metrics=request.require_complete_metrics,
    )


def prepare_revision(database: Any, book_id: str, request: Any) -> dict[str, Any]:
    return create_revision_handoff(
        database,
        book_id,
        edition_id=request.edition_id,
        requested_stage=request.requested_stage,
        require_complete_metrics=request.require_complete_metrics,
    )
