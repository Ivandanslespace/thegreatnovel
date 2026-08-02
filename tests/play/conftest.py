from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.campaign.conftest import make_projection_bundle, make_world_bundle
from tgn.campaign import create_campaign
from tgn.story.common import canonical_bytes


@pytest.fixture
def play_context(tmp_path: Path) -> dict[str, Path]:
    world = make_world_bundle(tmp_path, name="world")
    projection = make_projection_bundle(tmp_path, world)
    return {
        "root": tmp_path,
        "world": world,
        "projection": projection,
        "workspace": tmp_path / "play",
    }


def response_for(request: dict[str, Any], *, prose: str = "A public consequence became visible.") -> dict[str, Any]:
    return {
        "schema_version": 1,
        "narration_request_id": request["narration_request_id"],
        "narration_request_hash": request["narration_request_hash"],
        "locale": request["narration_locale"],
        "claims": request["claim_requirements"],
        "prose": prose,
    }


def write_response(path: Path, request: dict[str, Any], *, prose: str = "A public consequence became visible.") -> Path:
    path.write_bytes(canonical_bytes(response_for(request, prose=prose)))
    return path


def write_narrator(path: Path, *, fail_first: bool = False, fail_on_call: int | None = None) -> Path:
    marker = path.with_suffix(".marker")
    marker_text = repr(str(marker))
    if fail_on_call is not None:
        failure = (
            f"from pathlib import Path\n"
            f"marker = Path({marker_text})\n"
            "call_count = int(marker.read_text(encoding='utf-8')) if marker.exists() else 0\n"
            "call_count += 1\n"
            "marker.write_text(str(call_count), encoding='utf-8')\n"
            f"if call_count == {fail_on_call}:\n"
            "    raise SystemExit(9)\n"
        )
    elif fail_first:
        failure = (
            f"from pathlib import Path\n"
            f"marker = Path({marker_text})\n"
            "if not marker.exists():\n"
            "    marker.write_text('failed', encoding='utf-8')\n"
            "    raise SystemExit(9)\n"
        )
    else:
        failure = ""
    path.write_text(
        "import json, sys\n"
        f"{failure}"
        "request = json.load(sys.stdin)\n"
        "response = {'schema_version': 1, 'narration_request_id': request['narration_request_id'], "
        "'narration_request_hash': request['narration_request_hash'], 'locale': request['narration_locale'], "
        "'claims': request['claim_requirements'], 'prose': ('ظهرت نتيجة' if request['narration_locale'] == 'ar' else '中文后果')}\n"
        "sys.stdout.write(json.dumps(response, ensure_ascii=False, sort_keys=True, separators=(',', ':')))\n",
        encoding="utf-8",
    )
    return path


def create_campaign_for_context(context: dict[str, Path], *, name: str = "campaign", campaign_id: str = "campaign-001") -> Path:
    campaign = context["workspace"] / name
    context["workspace"].mkdir(parents=True, exist_ok=True)
    create_campaign(
        campaign,
        world_bundle_dir=context["world"],
        projection_bundle_dir=context["projection"],
        campaign_id=campaign_id,
        actor_id="player",
        max_decisions=20,
    )
    return campaign


def narrator_argv(script: Path, *extra: str) -> list[str]:
    return [sys.executable, str(script), *extra]
