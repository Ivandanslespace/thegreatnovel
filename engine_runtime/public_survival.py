"""全民求生合同的公开状态与逐回合推进。

本模块不创造主题、角色或能力文本：这些内容均来自新世界创建时的
``public_survival`` 与 ``player_talent``。它只把已经创作好的公开规则、
同区玩家和主角表现投影成可重放的状态。
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping


PUBLIC_STATE_KEYS = (
    "population_state",
    "public_system_state",
    "market_state",
    "ranking_state",
    "comparative_state",
    "rival_state",
)


def collective_contract(world: Mapping[str, Any]) -> dict[str, Any] | None:
    """返回已启用的全民合同；旧存档的字符串合同一律视作未启用。"""
    contract = world.get("genre_contract", {}) if isinstance(world, Mapping) else {}
    if not isinstance(contract, Mapping) or not contract.get("collective_transmission"):
        return None
    return dict(contract)


def is_collective_world(world: Mapping[str, Any]) -> bool:
    return collective_contract(world) is not None


def _public_blueprint(world: Mapping[str, Any]) -> dict[str, Any]:
    value = world.get("public_survival", {}) if isinstance(world, Mapping) else {}
    return dict(value) if isinstance(value, Mapping) else {}


def _as_records(value: Any) -> list[dict[str, Any]]:
    return [deepcopy(dict(item)) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _competition(world: Mapping[str, Any]) -> dict[str, Any] | None:
    """读取本局已固化的竞争推进合同；不为旧档补任何全局参数。"""
    value = _public_blueprint(world).get("competition", {})
    return deepcopy(dict(value)) if isinstance(value, Mapping) else None


def _leaderboard_rows(peers: list[dict[str, Any]], player_rank: int) -> list[dict[str, Any]]:
    rows = []
    for index, peer in enumerate(peers, start=1):
        rows.append({
            "rank": index,
            "player_id": peer["id"],
            "name": peer["name"],
            "status": "alive",
            "visible_edge": peer.get("visible_edge", ""),
        })
    rows.append({"rank": player_rank, "player_id": "player", "name": "你", "status": "alive"})
    return rows


def initial_public_states(world: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """为新建的全民世界生成首个、可见且可审计的公共状态。"""
    contract = collective_contract(world)
    if not contract:
        return {
            "population_state": {}, "public_system_state": {}, "market_state": {},
            "ranking_state": {}, "comparative_state": {}, "rival_state": {},
        }

    blueprint = _public_blueprint(world)
    competition = _competition(world)
    if competition is None:
        # 仅保护旧档不被半升级；新建全民世界已在创建时被严格拒绝。
        return {
            "population_state": {}, "public_system_state": {}, "market_state": {},
            "ranking_state": {}, "comparative_state": {}, "rival_state": {},
        }
    peers = _as_records(blueprint.get("initial_peers"))
    region_size = max(len(peers) + 1, int(contract.get("region_size") or 1000))
    initial_percentile = float(competition["initial_percentile"])
    player_rank = max(1, min(region_size, region_size - round(region_size * initial_percentile / 100) + 1))
    public_system = contract.get("public_system", {}) if isinstance(contract.get("public_system", {}), Mapping) else {}
    initial_messages = _as_records(blueprint.get("starting_channel_messages"))
    for message in initial_messages:
        message.setdefault("turn", 1)

    return {
        "population_state": {
            "enabled": True,
            "region_name": blueprint.get("region_name", ""),
            "region_size": region_size,
            "alive_count": region_size,
            "deaths_total": 0,
            "visible_peers": peers,
            "turn_history": [],
        },
        "public_system_state": {
            "enabled": True,
            "system_name": blueprint.get("system_name", ""),
            "opening_announcement": blueprint.get("opening_announcement", ""),
            "opening_rules": deepcopy(blueprint.get("opening_rules", [])),
            "channel_feed": initial_messages,
            "system_announcements": [],
            "regional_chat_enabled": bool(public_system.get("regional_chat")),
            "announcements_enabled": bool(public_system.get("announcements")),
        },
        "market_state": {
            "market_enabled": bool(public_system.get("trading")),
            "available_vendors": [],
            "market_prices": {},
            "player_inventory_listings": [],
            "recent_transactions": [],
            "market_trends": {},
        },
        "ranking_state": {
            "rankings_enabled": bool(public_system.get("rankings")),
            "player_rank_global": None,
            "player_rank_regional": player_rank,
            "leaderboards": {"regional": _leaderboard_rows(peers, player_rank)},
            "rank_season_current": 1,
            "rank_season_end_turn": int(competition["rank_season_end_turn"]),
            "prestige_points": 0,
        },
        "comparative_state": {
            "player_comparison_baseline": {"percentile": initial_percentile, "summary": "尚未进行正式行动"},
            "performance_metrics_history": [],
            "best_performance_by_category": {},
            "comparison_partners": [peer["id"] for peer in peers],
            "comparison_last_updated": 1,
        },
        "rival_state": {
            "active_rivals": peers[:int(competition["active_rival_count"])],
            "rival_relationships": {peer["id"]: "unknown" for peer in peers[:int(competition["active_rival_count"])]},
            "rival_competitions_active": [],
            "rival_score_current": 0,
            "rival_score_target": 0,
            "rivalry_win_rate": 0.0,
            "last_rival_encounter": None,
        },
    }


def _action_score(result: Mapping[str, Any], competition: Mapping[str, Any]) -> float:
    resolution = result.get("resolution", {}) if isinstance(result.get("resolution", {}), Mapping) else {}
    outcome = str(resolution.get("outcome", ""))
    outcome_scores = competition["outcome_scores"]
    score = float(outcome_scores.get(outcome, 0))
    event = result.get("event", {}) if isinstance(result.get("event", {}), Mapping) else {}
    payload = event.get("data", {}) if isinstance(event.get("data", {}), Mapping) else {}
    score += float(competition["location_discovery_bonus"]) * len(payload.get("discover_locations", []) or [])
    score += float(competition["knowledge_bonus"]) * len(payload.get("knowledge_additions", []) or [])
    changes = payload.get("resource_changes", {}) if isinstance(payload.get("resource_changes", {}), Mapping) else {}
    positive_resources = sum(1 for value in changes.values() if isinstance(value, (int, float)) and value > 0)
    score += min(float(competition["positive_resource_bonus_cap"]), positive_resources)
    return score


def advance_public_states(state_data: Mapping[str, Any], action_result: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]] | None:
    """在主角完成一个正式行动后推进同区玩家，并产出玩家可读反馈。

    所有结果由当前快照和存档种子决定。调用方必须将返回状态作为
    ``PUBLIC_SYSTEM_ADVANCED`` 标准事件提交，不能直接改写 YAML。
    """
    world = state_data.get("world", {}) if isinstance(state_data.get("world", {}), Mapping) else {}
    if not collective_contract(world):
        return None
    competition = _competition(world)
    if competition is None:
        return None

    population = deepcopy(state_data.get("population_state", {}))
    public = deepcopy(state_data.get("public_system_state", {}))
    market = deepcopy(state_data.get("market_state", {}))
    ranking = deepcopy(state_data.get("ranking_state", {}))
    comparative = deepcopy(state_data.get("comparative_state", {}))
    rival = deepcopy(state_data.get("rival_state", {}))
    if not population.get("enabled") or not public.get("enabled"):
        # 只允许新世界用完整、已创作的合同进入群体模式，防止把旧档案半升级。
        return None

    meta = state_data.get("meta", {}) if isinstance(state_data.get("meta", {}), Mapping) else {}
    turn = int(meta.get("current_turn", 1))
    region_size = max(1, int(population.get("region_size") or 1))
    alive_before = max(1, int(population.get("alive_count") or region_size))
    seed = f"{meta.get('rng_seed', meta.get('world_name', 'world'))}|public|{turn}"
    roll = int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % 100
    losses = int(competition["losses_per_trigger"]) if roll >= float(competition["loss_roll_threshold"]) else 0
    losses = min(max(0, losses), max(0, alive_before - 1))
    alive_after = max(1, alive_before - losses)

    action_score = _action_score(action_result, competition)
    history = comparative.setdefault("performance_metrics_history", [])
    cumulative = float(history[-1].get("cumulative_score", 0)) if history and isinstance(history[-1], Mapping) else 0.0
    cumulative += action_score
    # 开局所有人从同一规则起跑；排名来自本局已提交表现，而非叙述的主观宣称。
    percentile = max(1, min(99, float(competition["initial_percentile"]) + cumulative * float(competition["percentile_per_score"])))
    player_rank = max(1, min(alive_after, alive_after - round(alive_after * percentile / 100) + 1))
    metric = {"turn": turn, "action_score": action_score, "cumulative_score": cumulative, "percentile": percentile, "regional_rank": player_rank}
    history.append(metric)

    population["alive_count"] = alive_after
    population["deaths_total"] = int(population.get("deaths_total", 0)) + losses
    population.setdefault("turn_history", []).append({"turn": turn, "alive_before": alive_before, "alive_after": alive_after, "deaths": losses})
    population["turn_history"] = population["turn_history"][-20:]

    ranking["player_rank_regional"] = player_rank
    leaderboard = ranking.setdefault("leaderboards", {}).setdefault("regional", [])
    if isinstance(leaderboard, list):
        player_row = next((row for row in leaderboard if isinstance(row, dict) and row.get("player_id") == "player"), None)
        if player_row is None:
            player_row = {"player_id": "player", "name": "你", "status": "alive"}
            leaderboard.append(player_row)
        player_row["rank"] = player_rank
        leaderboard.sort(key=lambda row: int(row.get("rank", region_size + 1)) if isinstance(row, Mapping) else region_size + 1)

    comparative["player_comparison_baseline"] = {"percentile": percentile, "summary": "本回合表现已计入区域排名"}
    comparative["comparison_last_updated"] = turn
    rival["rival_score_current"] = cumulative
    active_rivals = rival.get("active_rivals", []) if isinstance(rival.get("active_rivals", []), list) else []
    if active_rivals:
        rival["last_rival_encounter"] = {"turn": turn, "rival_id": active_rivals[0].get("id"), "relative_percentile": percentile}

    feedback = {
        "regional_statistics": {"region_name": population.get("region_name", ""), "alive_count": alive_after, "deaths_this_turn": losses},
        "peer_comparison": metric,
        "ranking_changes": [{"player": "你", "regional_rank": player_rank, "percentile": percentile}],
        "channel_feed": deepcopy(public.get("channel_feed", [])[-5:]),
        "system_announcements": deepcopy(public.get("system_announcements", [])[-3:]),
    }
    return {
        "population_state": population,
        "public_system_state": public,
        "market_state": market,
        "ranking_state": ranking,
        "comparative_state": comparative,
        "rival_state": rival,
    }, feedback


def public_snapshot(state_data: Mapping[str, Any]) -> dict[str, Any] | None:
    """输出给主持器的玩家可见公共界面，不携带内部种子或行动合同。"""
    world = state_data.get("world", {}) if isinstance(state_data.get("world", {}), Mapping) else {}
    if not collective_contract(world):
        return None
    public = state_data.get("public_system_state", {}) if isinstance(state_data.get("public_system_state", {}), Mapping) else {}
    population = state_data.get("population_state", {}) if isinstance(state_data.get("population_state", {}), Mapping) else {}
    ranking = state_data.get("ranking_state", {}) if isinstance(state_data.get("ranking_state", {}), Mapping) else {}
    comparative = state_data.get("comparative_state", {}) if isinstance(state_data.get("comparative_state", {}), Mapping) else {}
    return {
        "region_name": population.get("region_name", ""),
        "opening_announcement": public.get("opening_announcement", ""),
        "opening_rules": deepcopy(public.get("opening_rules", [])),
        "channel_feed": deepcopy(public.get("channel_feed", [])[-5:]),
        "regional_statistics": {"alive_count": population.get("alive_count"), "deaths_total": population.get("deaths_total", 0)},
        "player_rank_regional": ranking.get("player_rank_regional"),
        "leaderboard": deepcopy(ranking.get("leaderboards", {}).get("regional", [])[:5]) if isinstance(ranking.get("leaderboards", {}), Mapping) else [],
        "comparison": deepcopy(comparative.get("player_comparison_baseline", {})),
    }
