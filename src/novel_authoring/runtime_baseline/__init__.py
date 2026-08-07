"""Source-derived runtime knowledge kept outside Canon and SQLite state."""

from novel_authoring.runtime_baseline.hydration import (
    RuntimeHydrationError,
    discover_runtime_recall_candidates,
    hydrate_runtime_baseline,
)
from novel_authoring.runtime_baseline.models import (
    AvailablePayoff,
    BaselineCategory,
    BaselineEvidence,
    BaselineStatus,
    EarnedEntry,
    EarnedSurface,
    EffectiveRuntimeState,
    RuntimeBaseline,
    RuntimeBaselineEntry,
    RuntimeBaselineInput,
    RuntimeBaselineManifest,
    RuntimeStateRecord,
)
from novel_authoring.runtime_baseline.service import (
    RuntimeBaselineError,
    build_earned_surface,
    build_effective_runtime_state,
    build_runtime_baseline,
    latest_runtime_baseline,
    load_earned_surface,
    load_effective_runtime_state,
    load_runtime_baseline,
)

__all__ = [
    "AvailablePayoff",
    "BaselineCategory",
    "BaselineEvidence",
    "BaselineStatus",
    "EarnedEntry",
    "EarnedSurface",
    "EffectiveRuntimeState",
    "RuntimeBaseline",
    "RuntimeBaselineEntry",
    "RuntimeBaselineError",
    "RuntimeHydrationError",
    "RuntimeBaselineInput",
    "RuntimeBaselineManifest",
    "RuntimeStateRecord",
    "build_earned_surface",
    "build_effective_runtime_state",
    "build_runtime_baseline",
    "latest_runtime_baseline",
    "load_earned_surface",
    "load_effective_runtime_state",
    "load_runtime_baseline",
    "discover_runtime_recall_candidates",
    "hydrate_runtime_baseline",
]
