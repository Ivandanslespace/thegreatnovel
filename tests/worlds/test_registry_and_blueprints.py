from __future__ import annotations

import json
from pathlib import Path

import pytest

from tgn.worlds.registry import choose_world_for_prompt, list_worlds, load_world


ROOT = Path(__file__).resolve().parents[2]
WORLD_DIR = ROOT / "worlds"
WORLD_IDS = ("frost_harbor", "gray_court")
TOP_LEVEL = {
    "schema_version", "id", "title", "locale", "premise", "causal_model",
    "core_question", "control_deficit", "lever", "cycle", "initial_state",
    "actions", "processes", "milestones", "expansions",
}
ACTION_FIELDS = {
    "id", "label", "description", "tags", "time_cost", "visible_when",
    "legal_when", "costs", "check", "lever", "success", "failure",
    "known_risks", "unknowns", "opportunity_costs", "max_uses",
}
PATCH_OPS = {"set", "add", "append_unique", "remove", "merge"}
COND_OPS = {"all", "any", "not", "eq", "ne", "gte", "lte", "gt", "lt", "contains", "truthy"}
PATH_PREFIXES = ("player.", "actors.", "world.", "opportunities.", "metrics.")


def _world(world_id: str) -> dict:
    with (WORLD_DIR / f"{world_id}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _assert_condition(condition: object) -> None:
    assert isinstance(condition, dict) and len(condition) == 1
    operator, value = next(iter(condition.items()))
    assert operator in COND_OPS
    if operator in {"all", "any"}:
        assert isinstance(value, list)
        for item in value:
            _assert_condition(item)
    elif operator == "not":
        _assert_condition(value)
    elif operator in {"eq", "contains"}:
        assert isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
    elif operator in {"ne", "gte", "lte", "gt", "lt"}:
        assert isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
    elif operator == "truthy":
        assert isinstance(value, str)


def _assert_patches(value: object) -> None:
    assert isinstance(value, list)
    for patch in value:
        assert isinstance(patch, dict)
        assert patch["op"] in PATCH_OPS
        path = patch["path"]
        assert path == "unlocks" or path.startswith(PATH_PREFIXES)


def _assert_facts(value: object) -> None:
    assert isinstance(value, list)
    for fact in value:
        assert set(fact) == {"text", "visibility", "kind", "source"}
        assert fact["visibility"] in {"public", "player", "hidden"} or str(fact["visibility"]).startswith("actor:")


@pytest.mark.parametrize("world_id", WORLD_IDS)
def test_blueprint_shape_and_content_gates(world_id: str) -> None:
    world = _world(world_id)
    assert set(world) == TOP_LEVEL
    assert world["schema_version"] == "tgn.world.v1"
    assert world["id"] == world_id
    state = world["initial_state"]
    assert set(state) == {"player", "actors", "world", "opportunities", "unlocks", "metrics"}
    assert len(state["actors"]) >= 3
    assert len(state["opportunities"]) >= 3
    assert len(world["actions"]) >= 16
    assert len(world["processes"]) >= 2
    assert len(world["milestones"]) >= 3
    assert len(world["expansions"]) >= 1
    assert state["world"]["completed_milestones"] == []
    assert state["world"]["process_last_run"] == {}
    assert state["world"]["materialized_expansions"] == []

    action_ids = {action["id"] for action in world["actions"]}
    assert len(action_ids) == len(world["actions"])
    assert set(world["cycle"]["rule_legibility_actions"]) <= action_ids
    assert all(set(chain) <= action_ids and len(chain) >= 2 for chain in world["cycle"]["compounding_chains"])
    lever = world["lever"]
    assert set(lever["action_ids"]) <= action_ids
    assert any(world_action["lever"]["required"] for world_action in world["actions"] if world_action["id"] in lever["action_ids"])

    for action in world["actions"]:
        assert set(action) == ACTION_FIELDS
        assert isinstance(action["time_cost"], int) and action["time_cost"] > 0
        assert isinstance(action["max_uses"], int) and action["max_uses"] > 0
        _assert_condition(action["visible_when"])
        _assert_condition(action["legal_when"])
        _assert_patches(action["success"]["patches"])
        _assert_patches(action["failure"]["patches"])
        _assert_facts(action["success"]["facts"])
        _assert_facts(action["failure"]["facts"])
        _assert_patches(action["lever"]["extra_patches"])
        assert set(action["lever"]) == {"required", "extra_costs", "extra_patches"}
        assert set(action["check"]) == {"base", "terms", "lever_bonus"}
        for term in action["check"]["terms"]:
            assert set(term) == {"path", "multiplier"}
            assert term["path"].startswith(PATH_PREFIXES)

    for process in world["processes"]:
        assert set(process) == {"id", "actor_id", "interval_minutes", "first_due_minute", "when", "patches", "facts"}
        assert process["interval_minutes"] > 0
        _assert_condition(process["when"])
        _assert_patches(process["patches"])
        _assert_facts(process["facts"])
    for milestone in world["milestones"]:
        assert set(milestone) == {"id", "when", "once", "patches", "facts", "tier_to"}
        _assert_condition(milestone["when"])
        _assert_patches(milestone["patches"])
        _assert_facts(milestone["facts"])
        assert all(patch["path"] != "world.materialized_expansions" for patch in milestone["patches"])
    for expansion in world["expansions"]:
        assert set(expansion) == {"id", "trigger", "anchors", "candidate"}
        _assert_condition(expansion["trigger"])
        candidate = expansion["candidate"]
        assert set(candidate) == {"namespace", "state_patches", "actions", "processes", "milestones"}
        _assert_patches(candidate["state_patches"])
        candidate_action_ids = {action["id"] for action in candidate["actions"]}
        assert not candidate_action_ids & set(state["unlocks"])
        for action in candidate["actions"]:
            assert set(action) == ACTION_FIELDS
            assert isinstance(action["max_uses"], int) and action["max_uses"] > 0


def test_worlds_have_real_structural_difference() -> None:
    frost, gray = (_world(item) for item in WORLD_IDS)
    assert frost["causal_model"] != gray["causal_model"]
    assert set(frost["initial_state"]["world"]) != set(gray["initial_state"]["world"])
    frost_tags = {tag for action in frost["actions"] for tag in action["tags"]}
    gray_tags = {tag for action in gray["actions"] for tag in action["tags"]}
    assert {"supply", "maintenance"} <= frost_tags
    assert {"evidence", "contract"} <= gray_tags
    assert frost_tags != gray_tags
    assert frost["lever"]["id"] != gray["lever"]["id"]
    assert frost["cycle"]["compounding_chains"] != gray["cycle"]["compounding_chains"]


@pytest.mark.parametrize("world_id", WORLD_IDS)
def test_chance_calibration_and_fact_attribution(world_id: str) -> None:
    world = _world(world_id)
    all_actions = list(world["actions"])
    all_actions.extend(action for expansion in world["expansions"] for action in expansion["candidate"]["actions"])
    for action in all_actions:
        check = action["check"]
        assert 35 <= check["base"] <= 100
        assert 0 <= check["lever_bonus"] <= 25
        for branch in ("success", "failure"):
            if action[branch]["patches"]:
                assert action[branch]["facts"], f"{world_id}:{action['id']} {branch} lacks attribution"
    assert {"absolute_power", "effective_capacity", "relative_standing", "strategy_space"} <= set(world["initial_state"]["metrics"])


@pytest.mark.parametrize(
    ("world_id", "expected_caps"),
    [
        (
            "frost_harbor",
            {"inspect_grid": 3, "schedule_crew": 2, "rest": 8, "automate_pump": 2, "convene_council": 1, "sign_quota": 1},
        ),
        (
            "gray_court",
            {"gather_deposition": 3, "verify_chain": 3, "rest": 8, "bind_commitment": 2, "set_arbitration": 1, "draft_settlement": 1},
        ),
    ],
)
def test_action_use_caps_prevent_unbounded_progression(world_id: str, expected_caps: dict[str, int]) -> None:
    world = _world(world_id)
    actions = {action["id"]: action for action in world["actions"]}
    for action_id, cap in expected_caps.items():
        assert actions[action_id]["max_uses"] == cap
    for expansion in world["expansions"]:
        for action in expansion["candidate"]["actions"]:
            assert action["max_uses"] <= 4


@pytest.mark.parametrize("world_id", WORLD_IDS)
def test_expansion_trigger_is_engine_materialized(world_id: str) -> None:
    world = _world(world_id)
    expansion = world["expansions"][0]
    assert expansion["trigger"]
    for milestone in world["milestones"]:
        assert all(patch["path"] != "world.materialized_expansions" for patch in milestone["patches"])


def _condition_paths(value: object) -> list[tuple[str, object]]:
    found: list[tuple[str, object]] = []
    if isinstance(value, dict):
        for operator, rhs in value.items():
            if operator in {"all", "any"}:
                for item in rhs:
                    found.extend(_condition_paths(item))
            elif operator == "not":
                found.extend(_condition_paths(rhs))
            elif operator in {"eq", "contains", "ne", "gte", "lte", "gt", "lt"}:
                found.append((rhs[0], rhs[1]))
            elif operator == "truthy":
                found.append((rhs, True))
    return found


@pytest.mark.parametrize(
    ("world_id", "window_actions"),
    [
        ("frost_harbor", {"divert_barge": "low_tide_window", "open_cold_storage": "barge_arrival", "convene_council": "council_slot"}),
        ("gray_court", {"file_motion": "filing_window", "seek_witness": "witness_window", "set_arbitration": "arbitration_slot"}),
    ],
)
def test_opportunity_windows_are_path_bound_and_one_shot(world_id: str, window_actions: dict[str, str]) -> None:
    world = _world(world_id)
    actions = {action["id"]: action for action in world["actions"]}
    for action_id, window_id in window_actions.items():
        action = actions[action_id]
        used_path = f"opportunities.{window_id}.used"
        visible = _condition_paths(action["visible_when"])
        legal = _condition_paths(action["legal_when"])
        assert any(path == used_path and value == 1 for path, value in visible + legal)
        for branch in ("success", "failure"):
            assert any(patch["path"] == used_path and patch["value"] == 1 for patch in action[branch]["patches"])
    if world_id == "gray_court":
        file_motion = actions["file_motion"]
        bounds = _condition_paths(file_motion["visible_when"])
        assert ("world.minute", {"path": "opportunities.filing_window.open"}) in bounds
        assert ("world.minute", {"path": "opportunities.filing_window.close"}) in bounds


def test_gray_arbitration_reversal_patch_is_reachable() -> None:
    world = _world("gray_court")
    arbitration = next(action for action in world["actions"] if action["id"] == "set_arbitration")
    assert {patch["path"] for patch in arbitration["success"]["patches"]} >= {
        "metrics.relationship_reversal", "metrics.absolute_power", "metrics.effective_capacity",
    }
    milestone = next(item for item in world["milestones"] if item["id"] == "become_arbitration_setter")
    assert "metrics.relationship_reversal" in {
        path for condition in _condition_paths(milestone["when"]) for path, _ in [condition]
    }


def test_documented_routes_have_real_condition_edges() -> None:
    frost = _world("frost_harbor")
    gray = _world("gray_court")
    frost_actions = {a["id"]: a for a in frost["actions"]}
    gray_actions = {a["id"]: a for a in gray["actions"]}
    frost_route = ["inspect_grid", "trace_fault", "log_cause", "automate_pump", "schedule_crew", "audit_manifest", "rest", "convene_council", "sign_quota"]
    gray_route = ["rest", "gather_deposition", "verify_chain", "file_motion", "publish_affidavit", "seek_witness", "bind_commitment", "call_alliance", "set_arbitration", "draft_settlement", "audit_registry", "expose_conflict"]
    assert all(action_id in frost_actions for action_id in frost_route)
    assert all(action_id in gray_actions for action_id in gray_route)
    assert any(path == "metrics.ledger_accuracy" for path, _ in _condition_paths(frost_actions["automate_pump"]["visible_when"]))
    assert any(path == "metrics.relationship_reversal" for path, _ in _condition_paths(frost_actions["sign_quota"]["legal_when"]))
    assert any(path == "metrics.chain_integrity" for path, _ in _condition_paths(gray_actions["bind_commitment"]["visible_when"]))
    assert any(path == "metrics.alliance_depth" for path, _ in _condition_paths(gray_actions["set_arbitration"]["legal_when"]))
    assert "open_outer_route" in {item["id"] for item in frost["milestones"]}
    assert "open_concord_docket" in {item["id"] for item in gray["milestones"]}


def _get(state: dict, path: str):
    value = state
    for part in path.split("."):
        value = value[part]
    return value


def _set(state: dict, path: str, value) -> None:
    parts = path.split(".")
    target = state
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


def _rhs(state: dict, value):
    return _get(state, value["path"]) if isinstance(value, dict) and set(value) == {"path"} else value


def _eval_condition(state: dict, condition: dict) -> bool:
    operator, value = next(iter(condition.items()))
    if operator == "all":
        return all(_eval_condition(state, item) for item in value)
    if operator == "any":
        return any(_eval_condition(state, item) for item in value)
    if operator == "not":
        return not _eval_condition(state, value)
    if operator == "truthy":
        return bool(_get(state, value))
    left = _get(state, value[0])
    right = _rhs(state, value[1]) if isinstance(value, list) else None
    if operator == "eq":
        return left == right
    if operator == "ne":
        return left != right
    if operator == "gte":
        return left >= right
    if operator == "lte":
        return left <= right
    if operator == "gt":
        return left > right
    if operator == "lt":
        return left < right
    if operator == "contains":
        return right in left
    raise AssertionError(operator)


def _apply_route_patches(state: dict, patches: list[dict]) -> None:
    for patch in patches:
        path, op, value = patch["path"], patch["op"], patch.get("value")
        if op == "set":
            _set(state, path, value)
        elif op == "add":
            _set(state, path, _get(state, path) + value)
        elif op == "append_unique":
            current = _get(state, path)
            if value not in current:
                current.append(value)


def _activate_expansions(world: dict, state: dict) -> None:
    """Model the engine's atomic trigger: materialize only after the trigger is true."""
    for expansion in world["expansions"]:
        if expansion["id"] in state["world"]["materialized_expansions"]:
            continue
        if _eval_condition(state, expansion["trigger"]):
            state["world"]["materialized_expansions"].append(expansion["id"])
            _apply_route_patches(state, expansion["candidate"]["state_patches"])


def _run_route(world: dict, route: list[str]) -> dict:
    state = json.loads(json.dumps(world["initial_state"], ensure_ascii=False))
    actions = {item["id"]: item for item in world["actions"]}
    milestones = {item["id"]: item for item in world["milestones"]}
    for action_id in route:
        action = actions[action_id]
        assert _eval_condition(state, action["visible_when"])
        assert _eval_condition(state, action["legal_when"]), action_id
        _apply_route_patches(state, action["success"]["patches"])
        if action["lever"]["required"]:
            _apply_route_patches(state, action["lever"]["extra_patches"])
        state["world"]["minute"] += action["time_cost"]
        for milestone in milestones.values():
            if milestone["once"] and milestone["id"] not in state["world"]["completed_milestones"] and _eval_condition(state, milestone["when"]):
                _apply_route_patches(state, milestone["patches"])
        _activate_expansions(world, state)
    return state


def test_documented_routes_reach_reversal_tier_and_expansion() -> None:
    frost_route = ["inspect_grid", "trace_fault", "log_cause", "automate_pump", "schedule_crew", "audit_manifest", "rest", "convene_council", "sign_quota"]
    frost_state = _run_route(_world("frost_harbor"), frost_route)
    assert {"become_dispatch_steward", "cross_tier_three", "open_outer_route"} <= set(frost_state["world"]["completed_milestones"])
    assert frost_state["world"]["materialized_expansions"] == ["outer_ice_shelf"]
    assert "outer_ice_shelf" in frost_state["unlocks"]

    gray_route = ["rest", "gather_deposition", "verify_chain", "file_motion", "publish_affidavit", "seek_witness", "bind_commitment", "call_alliance", "set_arbitration", "draft_settlement", "audit_registry", "expose_conflict"]
    gray_state = _run_route(_world("gray_court"), gray_route)
    assert {"become_arbitration_setter", "enter_federal_circuit", "open_concord_docket"} <= set(gray_state["world"]["completed_milestones"])
    assert gray_state["world"]["materialized_expansions"] == ["federal_concord"]
    assert "federal_concord" in gray_state["unlocks"]


@pytest.mark.parametrize("world_id", WORLD_IDS)
def test_lever_ablation_changes_action_graph(world_id: str) -> None:
    world = _world(world_id)
    actions = {action["id"] for action in world["actions"]}
    ablated = actions - set(world["lever"]["action_ids"])
    assert ablated != actions
    assert set(world["cycle"]["rule_legibility_actions"]) & set(world["lever"]["action_ids"])


def test_registry_lists_and_selects_conservatively() -> None:
    assert list_worlds() == ["frost_harbor", "gray_court"]
    assert load_world("frost_harbor")["title"] == "霜港潮汐网"
    default = choose_world_for_prompt(None)
    assert default["world"]["id"] == "frost_harbor"
    assert default["selection_reasons"] and default["fit_warning"]
    frost = choose_world_for_prompt("潮汐港口的维护和供给调度")
    gray = choose_world_for_prompt("证据链、契约期限与仲裁联盟")
    assert frost["world"]["id"] == "frost_harbor"
    assert gray["world"]["id"] == "gray_court"
    assert "unique" in frost["fit_warning"] or "唯一" in frost["fit_warning"]
    with pytest.raises(FileNotFoundError):
        load_world("missing")


def test_registry_accepts_explicit_host_blueprint(tmp_path: Path) -> None:
    source = WORLD_DIR / "gray_court.json"
    target = tmp_path / "custom.json"
    target.write_bytes(source.read_bytes())
    result = choose_world_for_prompt("unrelated", blueprint_file=target)
    assert result["world"]["id"] == "gray_court"
    assert "explicit" in result["selection_reasons"][0]
