from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tgn.core.hashing import canonical_json
from tgn.projection import compile_projection_bundle
from tgn.worldgen import compile_bundle


def write_json(path: Path, value: Any) -> Path:
    path.write_text(canonical_json(value), encoding="utf-8")
    return path


def world_draft(
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


def make_world_bundle(
    root: Path,
    *,
    name: str = "world",
    seed: str = "campaign-seed",
    draft: dict[str, Any] | None = None,
) -> Path:
    request_path = write_json(
        root / f"{name}-request.json",
        {"schema_version": 1, "prompt": "生成一个有资源冲突的求生世界"},
    )
    draft_path = write_json(root / f"{name}-draft.json", draft or world_draft())
    output = root / name
    compile_bundle(request_path, draft_path, seed, output)
    return output


def make_projection_bundle(root: Path, world: Path, *, name: str = "projection", suffix: str = "") -> Path:
    worldpack_hash = json.loads(
        (world / "bundle.json").read_text(encoding="utf-8")
    )["worldpack_hash"]
    output = root / name
    compile_projection_bundle(world, projection_draft(worldpack_hash, suffix), output)
    return output


@pytest.fixture
def bundle_pair(tmp_path: Path) -> tuple[Path, Path]:
    world = make_world_bundle(tmp_path, name="world")
    projection = make_projection_bundle(tmp_path, world)
    return world, projection


@pytest.fixture
def campaign_factory(tmp_path: Path, bundle_pair: tuple[Path, Path]):
    world, projection = bundle_pair

    def create(
        *,
        name: str = "campaign",
        campaign_id: str = "campaign-001",
        actor_id: str = "player",
        max_decisions: int = 20,
        world_bundle_dir: Path = world,
        projection_bundle_dir: Path = projection,
    ) -> tuple[Path, dict[str, Any]]:
        from tgn.campaign import create_campaign

        target = tmp_path / name
        result = create_campaign(
            target,
            world_bundle_dir=world_bundle_dir,
            projection_bundle_dir=projection_bundle_dir,
            campaign_id=campaign_id,
            actor_id=actor_id,
            max_decisions=max_decisions,
        )
        return target, result

    return create


def campaign_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def file_snapshot(root: Path) -> dict[str, tuple[str, int, int]]:
    import hashlib

    result: dict[str, tuple[str, int, int]] = {}
    for path in campaign_files(root):
        relative = path.relative_to(root).as_posix()
        stat = path.stat()
        result[relative] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns)
    return result


def choice_for(request: dict[str, Any], action_type: str) -> dict[str, Any]:
    return next(choice for choice in request["choices"] if choice["action_type"] == action_type)
