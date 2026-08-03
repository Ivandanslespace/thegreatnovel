"""Stable public failures for the local chat protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TGNError(Exception):
    code: str
    message: str
    recoverable: bool = False
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "recoverable": self.recoverable,
            "retryable": self.retryable,
            "details": self.details,
        }


def error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, TGNError):
        public = error
    else:
        public = TGNError(
            code="INTERNAL_ERROR",
            message="本地游戏引擎遇到未分类错误。",
            recoverable=False,
            retryable=False,
            details={"exception_type": type(error).__name__},
        )
    return {"protocol": "tgn.local.v1", "ok": False, "error": public.to_dict()}

