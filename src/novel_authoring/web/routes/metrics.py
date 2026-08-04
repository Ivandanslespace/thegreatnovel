from __future__ import annotations

from typing import Any

from novel_authoring.metrics.service import AuthorMetricInputService, ObservationInput
from novel_authoring.web.schemas import AuthorInputRequest


def save_author_input(
    database: Any, book_id: str, edition_id: str, request: AuthorInputRequest
) -> dict[str, Any]:
    observation = ObservationInput(
        book_id=book_id,
        edition_id=edition_id,
        **request.model_dump(mode="json"),
    )
    return AuthorMetricInputService(database).save(observation)


def missing_inputs(database: Any, book_id: str, edition_id: str, scope_id: str) -> dict[str, Any]:
    result = (
        __import__("novel_authoring.metrics.service", fromlist=["MetricsAssembler"])
        .MetricsAssembler(database)
        .rebuild(book_id, edition_id=edition_id, scope_type="CHAPTER", scope_id=scope_id)
    )
    return {
        "run_id": result["run_id"],
        "missing": {
            item["metric_id"]: item["missing_components"]
            for item in result["results"]
            if item["missing_components"]
        },
    }
