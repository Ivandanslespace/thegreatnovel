from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from tgn.core.hashing import canonical_json
from tgn.worldgen import compile_bundle, compile_world


def request_payload(prompt: str = "生成一个有资源冲突的求生世界") -> dict[str, Any]:
    return {"schema_version": 1, "prompt": prompt}


def draft_payload(
    *,
    world_id: str = "neon-spine-city",
    locale: str = "zh-CN",
    title: str = "霓虹脊城",
    premise: str = "一座履带城市穿过被酸雨吞没的荒原。",
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "mechanics_profile": "phase75_expedition_v1",
        "world_id": world_id,
        "content_locale": locale,
        "title": title,
        "premise": premise,
        "labels": labels
        or {
            "base": "履带城",
            "target": "淹没的旧地铁",
            "resource": "残余能源芯",
            "hazard": "机械寄生潮",
            "named_actor": "弥拉",
            "named_actor_role": "外层维护员",
            "named_actor_public_goal": "调查城外的异常信号",
        },
    }


def write_json(path: Path, value: Any) -> Path:
    path.write_text(canonical_json(value), encoding="utf-8")
    return path


@pytest.fixture
def sample_request() -> dict[str, Any]:
    return request_payload()


@pytest.fixture
def sample_draft() -> dict[str, Any]:
    return draft_payload()


@pytest.fixture
def input_files(tmp_path: Path, sample_request, sample_draft):
    request_path = write_json(tmp_path / "world_request.json", sample_request)
    draft_path = write_json(tmp_path / "world_draft.json", sample_draft)
    return request_path, draft_path


@pytest.fixture
def compilation(sample_request, sample_draft):
    return compile_world(sample_request, sample_draft, "same-seed")


@pytest.fixture
def bundle_dir(tmp_path: Path, input_files):
    request_path, draft_path = input_files
    output = tmp_path / "compiled" / "sample"
    compile_bundle(request_path, draft_path, "same-seed", output)
    return output


@pytest.fixture
def copied_draft(sample_draft):
    return copy.deepcopy(sample_draft)
