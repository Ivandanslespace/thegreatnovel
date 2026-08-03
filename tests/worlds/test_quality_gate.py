from __future__ import annotations

from copy import deepcopy

import pytest

from tgn.blueprint import compile_blueprint
from tgn.worlds import ExperienceGateError, load_world, require_experience_ready, validate_experience


@pytest.mark.parametrize("world_id", ["frost_harbor", "gray_court"])
def test_built_in_worlds_pass_runtime_experience_gate(world_id: str) -> None:
    compiled = compile_blueprint(load_world(world_id))
    report = require_experience_ready(compiled)
    assert report["passed"] is True
    assert report["counts"]["actions"] >= 16
    assert report["warnings"][0]["code"] == "semantic_review_required"


def test_gate_rejects_unbounded_and_runtime_type_unsafe_action() -> None:
    compiled = compile_blueprint(load_world("gray_court"))
    bad = deepcopy(compiled)
    del bad["actions"][0]["max_uses"]
    bad["actions"][0]["success"]["patches"].append(
        {"op": "add", "path": "world.public_case", "value": 1}
    )
    report = validate_experience(bad)
    assert report["passed"] is False
    assert {issue["code"] for issue in report["issues"]} >= {"unbounded_action", "nonnumeric_add_target"}
    with pytest.raises(ExperienceGateError):
        require_experience_ready(bad)
