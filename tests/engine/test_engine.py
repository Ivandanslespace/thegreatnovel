from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path

import pytest

from tgn.blueprint import BlueprintError, compile_blueprint
from tgn.engine import apply_event, initial_state, legal_actions, preview_action, resolve_action, validate_expansion
from tgn.projection import project_player_view


def make_world() -> dict:
    def action(action_id: str, *, lever=None, success=None, time=10):
        return {
            "id": action_id,
            "label": action_id,
            "description": "an action",
            "tags": [],
            "time_cost": time,
            "visible_when": None,
            "legal_when": None,
            "costs": {"player.energy": 1} if action_id == "work" else {},
            "check": {"base": 100, "terms": [], "lever_bonus": 0},
            "lever": {"required": lever.get("required", False), "extra_costs": [], "extra_patches": []} if lever else None,
            "success": {"patches": success or [{"op": "add", "path": "metrics.progress", "value": 1}], "facts": []},
            "failure": {"patches": [{"op": "add", "path": "metrics.failures", "value": 1}], "facts": []},
            "known_risks": ["fatigue"],
            "unknowns": ["weather"],
            "opportunity_costs": ["another window"],
            "max_uses": 1 if action_id == "work" else None,
        }

    return {
        "schema_version": "tgn.world.v1",
        "id": "test-world",
        "title": "Test",
        "locale": "zh",
        "premise": "p",
        "causal_model": "c",
        "core_question": "q",
        "control_deficit": "d",
        "lever": {"id": "ledger", "name": "ledger", "summary": "ledger", "cost": ["time"], "limits": ["evidence"], "ordinary_baseline": "baseline", "action_ids": ["work"]},
        "cycle": {
            "rule_legibility_actions": ["work"],
            "compounding_chains": [["work", "reverse"], ["work", "reverse"]],
            "relationship_reversal_milestone": "reverse",
            "tier_ascent_milestone": "tier",
            "larger_world_expansion": "larger",
        },
        "initial_state": {
            "player": {"energy": 4},
            "actors": {"clockkeeper": {"name": "clockkeeper"}},
            "world": {},
            "opportunities": {},
            "unlocks": [],
            "metrics": {"progress": 0},
        },
        "actions": [action("work", lever={"required": True}), action("remote", success=[{"op": "set", "path": "world.open", "value": True}])],
        "processes": [{"id": "clock", "actor_id": "clockkeeper", "interval_minutes": 5, "first_due_minute": 5, "when": None, "patches": [{"op": "add", "path": "metrics.ticks", "value": 1}], "facts": []}],
        "milestones": [
            {"id": "reverse", "when": {"gte": ["metrics.progress", 1]}, "patches": [], "facts": [], "once": True, "tier_to": None},
            {"id": "tier", "when": {"gte": ["metrics.progress", 1]}, "patches": [], "facts": [], "once": True, "tier_to": 1},
        ],
        "expansions": [{"id": "larger", "trigger": {"truthy": "world.open"}, "anchors": ["tier"], "candidate": {"namespace": "larger", "state_patches": [], "actions": [], "processes": [], "milestones": []}}],
    }


@pytest.fixture
def compiled():
    return compile_blueprint(make_world())


def test_compile_is_deep_copy_and_fail_closed(compiled):
    original = make_world()
    result = compile_blueprint(original)
    assert "blueprint_hash" in result
    result["initial_state"]["player"]["energy"] = 999
    assert original["initial_state"]["player"]["energy"] == 4
    bad = deepcopy(original)
    bad["actions"][0]["unexpected"] = True
    with pytest.raises(BlueprintError):
        compile_blueprint(bad)


def test_compile_rejects_global_candidate_id_collision():
    raw = make_world()
    raw["expansions"][0]["candidate"]["actions"] = [deepcopy(raw["actions"][0])]
    with pytest.raises(BlueprintError, match="duplicate global"):
        compile_blueprint(raw)


def test_preview_resolve_and_replay(compiled):
    state = initial_state(compiled, "campaign", 11)
    before = deepcopy(state)
    preview = preview_action(compiled, state, "work")
    assert preview.legal and preview.expected_state_hash
    assert state == before
    resolution = resolve_action(compiled, state, preview.preview_token, "request-1")
    replay = deepcopy(state)
    for event in resolution.events:
        replay = apply_event(replay, event)
    assert replay == resolution.new_state
    assert resolution.events[0].details["rng_draw"] if "rng_draw" in resolution.events[0].details else True
    assert resolution.events[0].details["time_after"] == resolution.new_state["world"]["minute"]
    assert all("fact_id" not in fact for event in resolution.events for fact in event.facts)
    assert all("event_id" not in event.details and "event_hash" not in event.details for event in resolution.events)
    process_events = [event for event in resolution.events if event.event_type == "PROCESS_TICK"]
    assert process_events and process_events[0].actor_id == "clockkeeper"
    assert process_events[0].details["process_id"] == "clock"


def test_stale_and_tampered_preview_are_rejected(compiled):
    state = initial_state(compiled, "campaign", 1)
    preview = preview_action(compiled, state, "work")
    changed = deepcopy(state)
    changed["player"]["energy"] = 3
    with pytest.raises(ValueError, match="stale_preview"):
        resolve_action(compiled, changed, preview.preview_token, "request")
    with pytest.raises(ValueError, match="tampered_preview"):
        resolve_action(compiled, state, preview.preview_token + "x", "request")
    encoded, signature = preview.preview_token.rsplit(".", 1)
    payload = json.loads(encoded)
    payload["use_lever"] = False
    forged = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "." + signature
    with pytest.raises(ValueError, match="tampered_preview"):
        resolve_action(compiled, state, forged, "request")


def test_knowledge_redaction_and_lazy_request(compiled):
    state = initial_state(compiled, "campaign", 1)
    events = ({"facts": ({"text": "public", "visibility": "public", "kind": "k", "source": "s"}, {"text": "secret", "visibility": "hidden", "kind": "k", "source": "s"})},)
    view = project_player_view(compiled, state, events)
    assert [f["text"] for f in view["facts"]] == ["public"]
    request = validate_expansion(compiled, "larger", None)
    assert request["type"] == "expansion_request"


def test_projection_whitelists_campaign_actor_and_world(compiled):
    state = initial_state(compiled, "campaign", 1)
    state["campaign"]["seed"] = "secret-seed"
    state["campaign"]["worldpack_hash"] = "secret-world-hash"
    state["actors"] = {"a": {"name": "公开人", "role": "clerk", "secret_fact": "hidden", "goal": "hidden"}}
    state["world"].update({"process_last_run": {"x": 1}, "active_actions": ["secret"], "action_counts": {"work": 1}, "public_note": "visible", "private": {"visibility": "hidden", "value": 1}})
    projected = project_player_view(compiled, state)["player_observation"]["state"]
    assert projected["campaign"] == {"status": "active", "turn": 0, "time_minute": 0, "current_tier": 0}
    assert projected["actors"][0]["name"] == "公开人" and "secret_fact" not in projected["actors"][0]
    assert projected["world"]["public_note"] == "visible" and "process_last_run" not in projected["world"] and "action_counts" not in projected["world"]


def test_projection_actor_order_is_canonical(compiled):
    state = initial_state(compiled, "campaign", 1)
    state["actors"] = {
        "zeta": {"name": "后录入"},
        "alpha": {"name": "先排序"},
    }
    actors = project_player_view(compiled, state)["player_observation"]["state"]["actors"]
    assert [actor["id"] for actor in actors] == ["alpha", "zeta"]


def test_lever_ablation_changes_legal_actions(compiled):
    state = initial_state(compiled, "campaign", 1)
    assert "work" in {a["id"] for a in legal_actions(compiled, state)}
    assert preview_action(compiled, state, "work", use_lever=False).reason_code == "lever_required"


def test_duplicate_cost_paths_are_aggregated(compiled):
    compiled["actions"][0]["costs"] = [{"path": "player.energy", "amount": 1}]
    compiled["actions"][0]["lever"]["extra_costs"] = [{"path": "player.energy", "amount": 1}]
    state = initial_state(compiled, "campaign", 1)
    state["player"]["energy"] = 1
    preview = preview_action(compiled, state, "work")
    assert not preview.legal and preview.reason_code == "insufficient_resource"


def test_action_max_uses_is_atomic_and_blocks_repeat(compiled):
    state = initial_state(compiled, "campaign", 1)
    preview = preview_action(compiled, state, "work")
    resolution = resolve_action(compiled, state, preview.preview_token, "first")
    assert resolution.new_state["world"]["action_counts"]["work"] == 1
    assert preview_action(compiled, resolution.new_state, "work").reason_code == "max_uses_reached"


def test_initial_tier_comes_from_world_tier(compiled):
    compiled["initial_state"]["world"]["tier"] = 2
    state = initial_state(compiled, "campaign", 1)
    assert state["campaign"]["current_tier"] == 2


def test_rng_is_independent_of_request_id(compiled):
    state = initial_state(compiled, "campaign", 1)
    token = preview_action(compiled, state, "work").preview_token
    left = resolve_action(compiled, state, token, "request-a")
    right = resolve_action(compiled, state, token, "request-b")
    assert left.events[0].details["rng_draw"] == right.events[0].details["rng_draw"]
    assert left.events[0].details["success"] == right.events[0].details["success"]
    assert left.events[0].details["draft_hash"] != right.events[0].details["draft_hash"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda candidate: candidate.update({"actions": [None]}),
        lambda candidate: candidate.update({"milestones": [None]}),
        lambda candidate: candidate.update({"state_patches": [None]}),
        lambda candidate: candidate.update({"state_patches": [{"op": "explode", "path": "world.x", "value": 1}]}),
    ],
)
def test_expansion_validation_fail_closed_for_malformed_candidate(compiled, mutator):
    candidate = {
        "parent_hash": compiled["blueprint_hash"],
        "namespace": "larger",
        "anchors": ["tier"],
        "state_patches": [],
        "actions": [],
        "processes": [],
        "milestones": [],
    }
    mutator(candidate)
    result = validate_expansion(compiled, "larger", candidate)
    assert result["valid"] is False and result["reason_code"]


def test_expansion_trigger_does_not_require_anchor_names(compiled):
    state = initial_state(compiled, "campaign", 1)
    state["world"]["open"] = True
    state["world"]["completed_milestones"] = []
    preview = preview_action(compiled, state, "remote")
    resolution = resolve_action(compiled, state, preview.preview_token, "expansion")
    expansion = [event for event in resolution.events if event.event_type == "EXPANSION_ACTIVATED"]
    assert expansion and expansion[0].details["anchors"] == ["tier"]


@pytest.mark.parametrize("world_name", ["frost_harbor.json", "gray_court.json"])
def test_real_world_fixtures_compile_when_configured(world_name):
    fixture_dir = os.environ.get("TGN_WORLD_FIXTURE_DIR")
    if not fixture_dir:
        pytest.skip("TGN_WORLD_FIXTURE_DIR not configured")
    path = Path(fixture_dir) / world_name
    assert path.is_file(), path
    compiled = compile_blueprint(json.loads(path.read_text(encoding="utf-8")))
    assert compiled["schema_version"] == "tgn.world.v1"
    assert compiled["blueprint_hash"].startswith("sha256:")
