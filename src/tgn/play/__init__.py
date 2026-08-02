"""Phase PC1 thin local human and external-narrator play loop."""

from .common import PlayError
from .service import DEFAULT_VOICE_ID, PlayService

__all__ = ["DEFAULT_VOICE_ID", "PlayError", "PlayService"]
