"""Deterministic runtime context routing."""

from novel_authoring.context.router import (
    ContextPurpose,
    DistillationSoftContext,
    RuntimeContextBundle,
    RuntimeContextRequest,
    route_runtime_context,
)

__all__ = [
    "ContextPurpose",
    "DistillationSoftContext",
    "RuntimeContextBundle",
    "RuntimeContextRequest",
    "route_runtime_context",
]
