from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGED_CONFIG_PATH = Path(__file__).resolve().with_name("default.yaml")
DEFAULT_CONFIG_PATH = (
    PACKAGED_CONFIG_PATH
    if PACKAGED_CONFIG_PATH.is_file()
    else PROJECT_ROOT / "config" / "default.yaml"
)


class IngestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extensions: list[str] = Field(default_factory=lambda: [".txt", ".md"])
    encodings: list[str] = Field(default_factory=lambda: ["utf-8", "utf-8-sig", "gb18030"])
    chapter_patterns: list[str]
    volume_patterns: list[str] = Field(default_factory=list)


class MetricConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    values: dict[str, Any] = Field(default_factory=dict)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_mode: str = "faithful_continuation"
    recent_full_chapters: int = 3
    ingest: IngestConfig
    metrics: dict[str, Any] = Field(default_factory=dict)
    rhythm: dict[str, Any] = Field(default_factory=dict)
    atlas: dict[str, Any] = Field(default_factory=dict)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(path: Path | None = None) -> Settings:
    with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if path is not None:
        with path.open("r", encoding="utf-8") as handle:
            override = yaml.safe_load(handle) or {}
        data = _deep_merge(data, override)
    return Settings.model_validate(data)
