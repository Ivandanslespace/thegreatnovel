"""Deterministic runtime context routing."""

from novel_authoring.context.router import (
    ContextPurpose,
    RuntimeContextBundle,
    RuntimeContextRequest,
    route_runtime_context,
)

__all__ = [
    "ContextPurpose",
    "RuntimeContextBundle",
    "RuntimeContextRequest",
    "route_runtime_context",
]
