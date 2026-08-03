"""Public V1-A Genesis requirement-evaluation boundary."""

from .catalog import CATALOG_VERSION, DEFAULT_CATALOG, REAL_RUNTIME_FEATURE_IDS, CatalogFeature, FeatureSupportCatalog
from .evaluator import evaluate
from .models import (
    ACCEPTANCE_POLICIES,
    APPROVAL_DECISIONS,
    CATALOG_LAYERS,
    DISPOSITIONS,
    ERROR_CODES,
    FeatureRequirementReport,
    GenesisRequest,
    GenesisValidationError,
    Requirement,
    RequirementApproval,
    RequirementCoverageApproval,
    RequirementProposal,
    RequirementReportItem,
    REPORT_SCHEMA_VERSION,
    SUPPORT_STATUSES,
)

__all__ = [
    "ACCEPTANCE_POLICIES",
    "APPROVAL_DECISIONS",
    "CATALOG_LAYERS",
    "CATALOG_VERSION",
    "DISPOSITIONS",
    "DEFAULT_CATALOG",
    "ERROR_CODES",
    "CatalogFeature",
    "FeatureRequirementReport",
    "FeatureSupportCatalog",
    "GenesisRequest",
    "GenesisValidationError",
    "Requirement",
    "RequirementApproval",
    "RequirementCoverageApproval",
    "RequirementProposal",
    "RequirementReportItem",
    "REAL_RUNTIME_FEATURE_IDS",
    "REPORT_SCHEMA_VERSION",
    "SUPPORT_STATUSES",
    "evaluate",
]
