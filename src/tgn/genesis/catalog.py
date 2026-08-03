"""Finite, versioned Feature Support Catalog for Genesis V1-A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .models import (
    CATALOG_LAYERS,
    _canonical_json,
    _fail,
    _validate_id,
    _validate_text,
)


# These are deliberately small, real boundary contracts.  They are not a
# registry of future gameplay features and do not imply runtime support.
CATALOG_VERSION = "genesis-catalog-v1"
# V1-A has no Genesis runtime implementation yet.  Keeping this allowlist
# empty makes it impossible for a caller to turn free-text evidence into a
# fake Runtime contract through a custom catalog.
REAL_RUNTIME_FEATURE_IDS = frozenset()


@dataclass(frozen=True, slots=True)
class CatalogFeature:
    feature_id: str
    layer: str
    contract_version: str = "1"
    evidence: tuple[str, ...] = ()
    supported: bool = True

    def __post_init__(self) -> None:
        _validate_id(self.feature_id, "$.feature_id")
        if type(self.layer) is not str or self.layer not in CATALOG_LAYERS:
            _fail("INVALID_VALUE", "$.layer", expected="CONTENT|RUNTIME|KERNEL|LEGACY", actual=self.layer)
        if self.layer in {"CONTENT", "RUNTIME"}:
            if not self.evidence:
                _fail("INVALID_VALUE", "$.evidence", expected="non-empty evidence for player-facing binding", actual=self.evidence)
        if self.layer == "RUNTIME" and self.feature_id not in REAL_RUNTIME_FEATURE_IDS:
            _fail("INVALID_VALUE", "$.feature_id", message="V1-A has no registered Runtime Feature contract")
        _validate_text(self.contract_version, "$.contract_version", max_length=32)
        if not isinstance(self.evidence, (list, tuple)):
            _fail("INVALID_TYPE", "$.evidence", expected="tuple of non-empty strings", actual=self.evidence)
        if len(self.evidence) > 64:
            _fail("INVALID_VALUE", "$.evidence", expected="array length <= 64", actual=self.evidence)
        for index, item in enumerate(self.evidence):
            _validate_text(item, f"$.evidence[{index}]", max_length=8192)
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if type(self.supported) is not bool:
            _fail("INVALID_TYPE", "$.supported", expected="boolean", actual=self.supported)

    @property
    def player_bindable(self) -> bool:
        return self.layer in {"CONTENT", "RUNTIME"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "layer": self.layer,
            "contract_version": self.contract_version,
            "evidence": list(self.evidence),
            "supported": self.supported,
        }


@dataclass(frozen=True, slots=True)
class FeatureSupportCatalog:
    version: str
    features: tuple[CatalogFeature, ...]

    def __post_init__(self) -> None:
        _validate_text(self.version, "$.version", max_length=128)
        if not isinstance(self.features, (list, tuple)):
            _fail("INVALID_TYPE", "$.features", expected="tuple of CatalogFeature", actual=self.features)
        if not self.features:
            _fail("INVALID_VALUE", "$.features", expected="non-empty finite catalog", actual=self.features)
        if any(type(item) is not CatalogFeature for item in self.features):
            _fail("INVALID_TYPE", "$.features", expected="CatalogFeature objects", actual=self.features)
        object.__setattr__(self, "features", tuple(sorted(self.features, key=lambda item: item.feature_id)))
        ids = [item.feature_id for item in self.features]
        if len(ids) != len(set(ids)):
            _fail("DUPLICATE_ID", "$.features", message="duplicate feature identifier")

    @classmethod
    def from_features(cls, version: str, features: Sequence[CatalogFeature]) -> "FeatureSupportCatalog":
        return cls(version=version, features=tuple(features))

    @classmethod
    def v1(cls) -> "FeatureSupportCatalog":
        """Return the finite V1 catalog with no unimplemented Runtime entries."""

        return cls(
            version=CATALOG_VERSION,
            features=(
                CatalogFeature(
                    "content.world_premise.v1",
                    "CONTENT",
                    evidence=("expression only; no runtime mechanic",),
                ),
                CatalogFeature(
                    "kernel.canonical_identity",
                    "KERNEL",
                    evidence=("Genesis artifact canonical identity primitive",),
                ),
                CatalogFeature(
                    "legacy.phase75_compatibility",
                    "LEGACY",
                    evidence=("read-only compatibility boundary for the frozen legacy profile",),
                ),
            ),
        )

    @property
    def entries(self) -> tuple[CatalogFeature, ...]:
        return self.features

    def get(self, feature_id: str) -> CatalogFeature | None:
        for feature in self.features:
            if feature.feature_id == feature_id:
                return feature
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"catalog_version": self.version, "features": [feature.to_dict() for feature in self.features]}

    @property
    def hash(self) -> str:
        # The hash is the canonical identity paired with the catalog version in
        # every V1-A Report lineage.
        from hashlib import sha256

        return sha256(_canonical_json(self.to_dict()).encode("utf-8")).hexdigest()


DEFAULT_CATALOG = FeatureSupportCatalog.v1()


__all__ = [
    "CATALOG_VERSION",
    "DEFAULT_CATALOG",
    "REAL_RUNTIME_FEATURE_IDS",
    "CatalogFeature",
    "FeatureSupportCatalog",
]
