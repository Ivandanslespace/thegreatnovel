"""Phase 9B1 bounded World Draft compilation boundary."""

from .compiler import (
    COMPILER_ID,
    MECHANICS_PROFILE,
    bootstrap_smoke,
    compile_world,
    compile_worldpack,
    load_document,
    materialize_initial_state,
    parse_strict_json,
    validate_documents,
    validate_request,
    validate_draft,
)
from .bundle import BUNDLE_FILES, compile_bundle, compile_devour_overlay_bundle, verify_bundle
from .devour_overlay import (
    BASE_COMPILER_ID,
    DEVOUR_OVERLAY_COMPILER_ID,
    DEVOUR_OVERLAY_ID,
    apply_devour_overlay,
    bootstrap_devour_overlay,
)
from .models import (
    BootstrapResult,
    CompiledWorldPack,
    CompilationResult,
    ValidationIssue,
    WorldDraft,
    WorldGenesisRequest,
    WorldGenError,
)

__all__ = [
    "COMPILER_ID",
    "MECHANICS_PROFILE",
    "BUNDLE_FILES",
    "BASE_COMPILER_ID",
    "DEVOUR_OVERLAY_COMPILER_ID",
    "DEVOUR_OVERLAY_ID",
    "BootstrapResult",
    "CompiledWorldPack",
    "CompilationResult",
    "ValidationIssue",
    "WorldDraft",
    "WorldGenesisRequest",
    "WorldGenError",
    "bootstrap_smoke",
    "compile_world",
    "compile_worldpack",
    "compile_bundle",
    "compile_devour_overlay_bundle",
    "apply_devour_overlay",
    "bootstrap_devour_overlay",
    "load_document",
    "materialize_initial_state",
    "parse_strict_json",
    "validate_documents",
    "validate_request",
    "validate_draft",
    "verify_bundle",
]
