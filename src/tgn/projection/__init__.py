"""Phase 9B2A detached Player-Visible Projection Map boundary."""

from .bundle import (
    PROJECTION_FILES,
    compile_projection_bundle,
    preview_projection,
    publication_lock_path,
    verify_projection_bundle,
)
from .compiler import (
    PROJECTION_COMPILER_ID,
    PROJECTION_DRAFT_LABEL_FIELDS,
    PROJECTION_SCHEMA_VERSION,
    build_initial_request,
    compile_projection,
    load_projection_draft,
    presentation_hash,
    projection_hash,
    validate_projection_draft,
)
from .models import (
    PlayerPresentation,
    PlayerProjectionMap,
    ProjectionCompilationResult,
    ProjectionDraft,
)
from .presenter import build_player_presentation

__all__ = [
    "PROJECTION_COMPILER_ID",
    "PROJECTION_DRAFT_LABEL_FIELDS",
    "PROJECTION_FILES",
    "PROJECTION_SCHEMA_VERSION",
    "PlayerPresentation",
    "PlayerProjectionMap",
    "ProjectionCompilationResult",
    "ProjectionDraft",
    "build_initial_request",
    "build_player_presentation",
    "compile_projection",
    "compile_projection_bundle",
    "load_projection_draft",
    "preview_projection",
    "presentation_hash",
    "projection_hash",
    "publication_lock_path",
    "validate_projection_draft",
    "verify_projection_bundle",
]
