from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tgn.core.hashing import canonical_json
from tgn.worldgen import compile_bundle


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


def projection_draft(source_hash: str, suffix: str = "") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_worldpack_hash": source_hash,
        "labels": {
            "secondary_resource": f"零件{suffix}",
            "phase_day": f"白昼{suffix}",
            "phase_night": f"夜晚{suffix}",
            "player_track": f"玩家成长{suffix}",
            "base_track": f"基地成长{suffix}",
            "site_condition_subject": f"地点状态{suffix}",
            "site_condition_unstable": f"不稳定{suffix}",
            "site_condition_safe": f"安全{suffix}",
            "actor_report_goal": f"待报告{suffix}",
            "actor_reported_goal": f"已报告{suffix}",
            "build_window_runner": f"窗口奔跑者{suffix}",
            "build_field_rest": f"野外休整{suffix}",
            "build_quick_rest": f"快速休整{suffix}",
        },
    }


@pytest.fixture
def source_bundle(tmp_path: Path) -> Path:
    request_path = write_json(tmp_path / "world_request.json", request_payload())
    draft_path = write_json(tmp_path / "world_draft.json", draft_payload())
    output = tmp_path / "source-bundle"
    compile_bundle(request_path, draft_path, "projection-seed", output)
    return output


@pytest.fixture
def source_worldpack_hash(source_bundle: Path) -> str:
    return json.loads((source_bundle / "bundle.json").read_text(encoding="utf-8"))["worldpack_hash"]


@pytest.fixture
def valid_projection_draft(source_worldpack_hash: str) -> dict[str, Any]:
    return projection_draft(source_worldpack_hash)


@pytest.fixture
def compiled_projection(source_bundle: Path, valid_projection_draft: dict[str, Any], tmp_path: Path):
    from tgn.projection import compile_projection, compile_projection_bundle

    result = compile_projection(source_bundle, valid_projection_draft)
    output = tmp_path / "projection-bundle"
    compile_projection_bundle(source_bundle, valid_projection_draft, output)
    return result, output
