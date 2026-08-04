from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from novel_authoring.config import PROJECT_ROOT
from novel_authoring.utils import json_dumps, sha256_bytes


class MetricScope(StrEnum):
    CHAPTER = "CHAPTER"
    WINDOW = "WINDOW"
    PROMISE = "PROMISE"
    THREAD = "THREAD"
    EDITION_STATE = "EDITION_STATE"
    CANDIDATE = "CANDIDATE"


class MetricSourceKind(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    DERIVED = "DERIVED"
    SEMANTIC_ESTIMATE = "SEMANTIC_ESTIMATE"
    AUTHOR_INPUT = "AUTHOR_INPUT"
    AUTHOR_OVERRIDE = "AUTHOR_OVERRIDE"
    UNKNOWN = "UNKNOWN"


class MissingPolicy(StrEnum):
    NULL = "NULL"
    PROVISIONAL = "PROVISIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComponentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = ""
    description: str = ""
    value_type: str = "number"
    minimum: float | None = None
    maximum: float | None = None
    allowed_source_kinds: list[MetricSourceKind]
    evidence_required: bool = False
    weight: float | None = None


class MetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_id: str
    display_name: str
    description: str
    scope: MetricScope
    formula_id: str
    result_range: tuple[float, float]
    required_components: list[str] = Field(default_factory=list)
    optional_components: list[str] = Field(default_factory=list)
    components: dict[str, ComponentDefinition]
    missing_policy: MissingPolicy = MissingPolicy.NULL
    minimum_completeness: float = Field(default=1.0, ge=0, le=1)
    web: dict[str, Any] = Field(default_factory=dict)
    evidence_policy: dict[str, Any] = Field(default_factory=dict)


class MetricsRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registry_version: int = 1
    metrics: dict[str, MetricDefinition]

    def model_post_init(self, __context: Any) -> None:
        if set(self.metrics) != {item.metric_id for item in self.metrics.values()}:
            raise ValueError("metrics 注册表 key 必须与 metric_id 一致")
        for metric in self.metrics.values():
            known = set(metric.components)
            required = set(metric.required_components)
            optional = set(metric.optional_components)
            if not required <= known or not optional <= known or required & optional:
                raise ValueError(f"指标 {metric.metric_id} 的 component 声明不一致")
            low, high = metric.result_range
            if low >= high:
                raise ValueError(f"指标 {metric.metric_id} 的 result_range 无效")
            for component_id, component in metric.components.items():
                if (
                    component.minimum is not None
                    and component.maximum is not None
                    and component.minimum > component.maximum
                ):
                    raise ValueError(f"component {metric.metric_id}.{component_id} 范围无效")

    @property
    def registry_hash(self) -> str:
        return sha256_bytes(json_dumps(self.model_dump(mode="json")).encode("utf-8"))

    def metric(self, metric_id: str) -> MetricDefinition:
        try:
            return self.metrics[metric_id]
        except KeyError as exc:
            raise ValueError(f"未知指标：{metric_id}") from exc

    def component(self, metric_id: str, component_id: str) -> ComponentDefinition:
        metric = self.metric(metric_id)
        try:
            return metric.components[component_id]
        except KeyError as exc:
            raise ValueError(f"未知 component：{metric_id}.{component_id}") from exc

    def validate_source(
        self, metric_id: str, component_id: str, source_kind: MetricSourceKind
    ) -> None:
        component = self.component(metric_id, component_id)
        if source_kind not in component.allowed_source_kinds:
            raise ValueError(f"{metric_id}.{component_id} 不允许 source_kind={source_kind.value}")


PACKAGED_REGISTRY_PATH = Path(__file__).resolve().with_name("metrics_registry.yaml")
DEFAULT_REGISTRY_PATH = (
    PROJECT_ROOT / "config" / "metrics_registry.yaml"
    if (PROJECT_ROOT / "config" / "metrics_registry.yaml").is_file()
    else PACKAGED_REGISTRY_PATH
)


def load_registry(path: Path | None = None) -> MetricsRegistry:
    selected = path or DEFAULT_REGISTRY_PATH
    with selected.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return MetricsRegistry.model_validate(payload)
