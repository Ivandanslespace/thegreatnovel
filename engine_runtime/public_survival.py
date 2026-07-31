"""全民求生合同的公开状态与逐回合推进。

本模块不创造主题、角色或能力文本：这些内容均来自新世界创建时的
``public_survival`` 与 ``player_talent``。它只把已经创作好的公开规则、
同区玩家和主角表现投影成可重放的状态。
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import random
from typing import Any, Mapping

from engine_runtime.ranking_engine import (
    calculate_cdf_percentile,
    calculate_dimension_scores,
    convert_percentile_to_rank,
)
from engine_runtime.channel_engine import generate_channel_messages
from engine_runtime.persistence import load_peer_agents
from engine_runtime.peer_agent import PeerAgent


def calculate_peer_capability(peer, action_type):
    """Calculate peer's effective capability for given action type based on their stats"""
    attrs = peer.attributes if hasattr(peer, 'attributes') else {}
    
    # Helper to get attribute with fallback default of 10
    def attr(name):
        if isinstance(attrs, dict):
            return float(attrs.get(name, 10))
        return 10.0
    
    if action_type == "COMBAT":
        return (attr("strength") * 0.4 +
                attr("agility") * 0.3 +
                (float(peer.profession_level) if hasattr(peer, 'profession_level') else 1) * 5 +
                (float(peer.level) if hasattr(peer, 'level') else 1) * 2)
    
    elif action_type == "EXPLORATION":
        return (attr("agility") * 0.3 +
                attr("spirit") * 0.3 +
                (float(peer.profession_level) if hasattr(peer, 'profession_level') else 1) * 5 +
                (float(peer.level) if hasattr(peer, 'level') else 1) * 2)
    
    elif action_type == "BUILD":
        return (attr("constitution") * 0.3 +
                attr("intelligence") * 0.4 +
                (float(peer.profession_level) if hasattr(peer, 'profession_level') else 1) * 5 +
                (float(peer.level) if hasattr(peer, 'level') else 1) * 2)
    
    elif action_type == "SOCIAL_INTERACTION":
        return (attr("charisma") * 0.5 +
                attr("empathy") * 0.3 +
                (float(peer.profession_level) if hasattr(peer, 'profession_level') else 1) * 5 +
                (float(peer.level) if hasattr(peer, 'level') else 1) * 2)
    
    # Fallback: average of all attributes
    if isinstance(attrs, dict) and len(attrs) > 0:
        return sum(float(v) for v in attrs.values()) / len(attrs)
    return 10.0


def select_action_by_personality(peer, available_actions, rng: random.Random | None = None):
    """Choose action based on peer's personality traits.

    P1-02: Accepts an optional deterministic *rng* so that replays with the
    same seed always produce identical action choices.  Falls back to the
    global ``random`` module only when no *rng* is supplied (legacy path).
    
    This function weights action selection based on the peer's 6-dimension
    personality profile, creating distinct behavioral patterns.
    
    Returns:
        str: Selected action type from available options
    """
    if rng is None:
        rng = random
    
    if not available_actions:
        return "EXPLORATION"
    
    # Extract personality traits with safe defaults
    traits = peer.personality_traits if hasattr(peer, 'personality_traits') else {}
    
    caution = traits.get("caution", 50)
    ambition = traits.get("ambition", 50)
    empathy = traits.get("empathy", 50)
    openness = traits.get("openness", 50)
    collectivism = traits.get("collectivism", 50)
    
    # Initialize equal weights for all possible actions
    weights = {
        "EXPLORATION": 1.0,
        "COMBAT": 1.0,
        "BUILD": 1.0,
        "SOCIAL_INTERACTION": 1.0
    }
    
    # --- Trait-based modifiers (P1 personality-strength fix) ---
    # Multipliers raised to 2.5-3.5x so that extreme personalities choose
    # their dominant action ≥70% of the time over a 20-turn window.
    
    # Cautious peers (high caution > 70): prefer building and avoiding risk
    if caution > 70:
        weights["BUILD"] *= 3.0
        weights["EXPLORATION"] *= 0.6
        weights["COMBAT"] *= 0.3
    elif caution < 30:  # Reckless peers
        weights["COMBAT"] *= 2.8
        weights["EXPLORATION"] *= 2.0
        weights["BUILD"] *= 0.5
    
    # Open/adventurous peers (high openness > 70): like trying new experiences
    if openness > 70:
        weights["EXPLORATION"] *= 2.5
        weights["COMBAT"] *= 1.5
        weights["SOCIAL_INTERACTION"] *= 1.2
    elif openness < 30:  # Traditional/closed peers
        weights["BUILD"] *= 2.5
        weights["SOCIAL_INTERACTION"] *= 1.8
    
    # Ambitious peers (high ambition > 70): seek high-reward risks
    if ambition > 70:
        weights["COMBAT"] *= 3.5
        weights["EXPLORATION"] *= 2.5
        weights["BUILD"] *= 0.5
    elif ambition < 30:  # Content peers
        weights["BUILD"] *= 2.8
        weights["SOCIAL_INTERACTION"] *= 1.8
    
    # Highly empathetic/social peers (high empathy > 70): prioritize social connections
    if empathy > 70:
        weights["SOCIAL_INTERACTION"] *= 3.0
        weights["BUILD"] *= 1.2
    
    # Collectivist peers (high collectivism > 70): group-focused behavior
    if collectivism > 70:
        weights["SOCIAL_INTERACTION"] *= 3.0
        weights["BUILD"] *= 1.4
        weights["EXPLORATION"] *= 0.7
    elif collectivism < 30:  # Individualist peers
        weights["EXPLORATION"] *= 2.5
        weights["COMBAT"] *= 2.0
    
    # Filter to only available actions
    filtered_weights = {action: weight for action, weight in weights.items() 
                       if action in available_actions}
    
    # Ensure we have at least one option
    if not filtered_weights:
        return rng.choice(available_actions)
    
    # Normalize weights for probability distribution
    total_weight = sum(filtered_weights.values())
    normalized = {k: v / total_weight for k, v in filtered_weights.items()}
    
    # Weighted random selection
    r = rng.random()
    cumulative = 0.0
    for action, weight in normalized.items():
        cumulative += weight
        if r <= cumulative:
            return action
    
    return list(normalized.keys())[-1]  # Fallback


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


def advance_public_states(state, action_result: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]] | None:
    """在主角完成一个正式行动后推进同区玩家，并产出玩家可读反馈。

    所有结果由当前快照和存档种子决定。调用方必须将返回状态作为
    ``PUBLIC_SYSTEM_ADVANCED`` 标准事件提交，不能直接改写 YAML。
    
    Args:
        state: GameState object from engine.state
        action_result: The execution result dictionary
    """
    # P0-01: Properly extract data from GameState for processing
    state_data = dict(state.data)
    
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

    # === PHASE 2: CDF 排名计算（替换旧的 fake formula）===
    # 计算主角本回合五维得分
    protag_dims = calculate_dimension_scores(dict(action_result))
        
    # LOAD peer agents from SQLite or return empty list if no store available
    campaign_id = state_data.get("meta", {}).get("campaign_id") or state_data.get("world", {}).get("name", "unknown")
    
    # P0-01: Always try to load peer agents from GameState's store
    peer_agents = load_peer_agents(state, campaign_id)
    
    # P1-03: Build per-action average scores from a rolling window of last 10
    # actions for both protagonist and peers, eliminating the systematic
    # degradation caused by comparing single-turn vs cumulative scores.
    WEIGHTS = {"combat": 0.0, "resources": 0.0, "base": 0.0, "information": 0.0, "social": 0.0}
    peer_avg_scores = []
    for peer in peer_agents:
        recent = peer.action_history[-10:]  # rolling window
        if recent:
            avg_dims = dict(WEIGHTS)
            scored_records = 0
            for record in recent:
                scores = record.get("scores") or record.get("dimensional_scores", {})
                if scores:
                    scored_records += 1
                    for dim in avg_dims:
                        avg_dims[dim] += scores.get(dim, 0.0)
            if scored_records:
                for dim in avg_dims:
                    avg_dims[dim] /= scored_records
            peer_avg_scores.append(avg_dims)
        else:
            peer_avg_scores.append(dict(WEIGHTS))

    percentile = calculate_cdf_percentile(protag_dims, peer_avg_scores)
    percentile = max(1.0, min(99.0, percentile))
    player_rank = convert_percentile_to_rank(percentile, alive_after)
    
    metric = {
        "turn": turn,
        "dimensional_scores": protag_dims,
        "percentile": percentile,
        "regional_rank": player_rank,
    }
    history = comparative.setdefault("performance_metrics_history", [])
    history.append(metric)
    # P1-05: Bound performance_metrics_history to last 100 entries to prevent save bloat
    if len(history) > 100:
        comparative["performance_metrics_history"] = history[-100:]

    # === PHASE 3: 频道消息生成（极简） ===
    # Simulate one action per peer with deterministic RNG based on capabilities
    peer_results = []

    for peer in peer_agents:
        # P1-02: Deterministic RNG seeded per-peer, per-turn for reproducible replays
        action_rng = random.Random(f"{peer.id}|{turn}|action_select")
        # 1. Pick random available action type
        available_actions = ["EXPLORATION", "COMBAT", "BUILD", "SOCIAL_INTERACTION"]
        
        # 2. Select based on personality/risk preference (deterministic via action_rng)
        chosen_type = select_action_by_personality(peer, available_actions, rng=action_rng)
        
        # 3. Calculate peer's capability
        capability = calculate_peer_capability(peer, chosen_type)
        
        # 4. Base difficulty (can be enhanced later per action/location)
        base_difficulty = 15.0
        
        # 5. Calculate success probability
        success_chance = min(0.95, max(0.05, capability / (base_difficulty * 1.5)))
        
        # 6. Deterministic roll using peer_id + turn as seed
        rng = random.Random(f"{peer.id}|{state_data['meta']['current_turn']}|{chosen_type}")
        roll = rng.random()
        
        # 7. Determine outcome based on roll vs chance
        if roll < success_chance * 0.7:
            outcome = "大成功"
            outcome_mult = 2.5
        elif roll < success_chance:
            outcome = "成功"
            outcome_mult = 1.0
        elif roll < success_chance + 0.2:
            outcome = "普通成功"
            outcome_mult = 0.6
        elif roll < success_chance + 0.4:
            outcome = "小失败"
            outcome_mult = 0.2
        else:
            outcome = "失败"
            outcome_mult = 0.0
        
        # 8. Generate dimensional scores based on action type and outcome
        mock_scores = {"combat": 0, "resources": 0, "base": 0, "information": 0, "social": 0}
        
        if chosen_type == "EXPLORATION":
            locations_found = int(outcome_mult)  # 2 for 大成功，1 for 成功，0 for fail/小失败
            mock_scores["information"] = locations_found * 25.0 * (outcome_mult / max(1, locations_found))
            
        elif chosen_type == "COMBAT":
            kills = int(outcome_mult) + 1
            mock_scores["combat"] = kills * 40.0 * (outcome_mult / kills)
            
        elif chosen_type == "BUILD":
            mock_scores["base"] = 20.0 * outcome_mult
            
        elif chosen_type == "SOCIAL_INTERACTION":
            mock_scores["social"] = 20.0 * outcome_mult
        
        peer_results.append({
            "peer_id": peer.id,
            "peer_name": peer.name,
            "action_type": chosen_type,
            "target": f"{chosen_type.lower()}_{peer.id}",
            "outcome": outcome,
            "dimensional_scores": mock_scores,
            "cumulative_score": sum(mock_scores.values())
        })
    new_msgs = generate_channel_messages(
        peer_results=peer_results,
        current_turn=turn,
        existing_feed=public.get("channel_feed", []),
        rng_seed=meta.get("rng_seed", meta.get("world_name", "world")),
    )
    public.setdefault("channel_feed", []).extend(new_msgs)
    # P1-04: Bound channel_feed to last 100 entries to prevent save bloat
    feed = public.get("channel_feed", [])
    if len(feed) > 100:
        public["channel_feed"] = feed[-100:]

    # === PHASE 4: Update peer states with new action records ===
    for result in peer_results:
        peer = next((p for p in peer_agents if p.id == result["peer_id"]), None)
        if peer:
            peer.record_action(
                turn=turn,
                action_type=result["action_type"],
                target=result["target"],
                outcome=result["outcome"],
                scores=result["dimensional_scores"]
            )
            
            # Persist back to SQLite using state object (not state_data dict)
            from engine_runtime.persistence import insert_peer_agent
            insert_peer_agent(state, campaign_id, peer)

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
    prev = float(rival.get("rival_score_current", 0) or 0)
    rival["rival_score_current"] = prev + sum(protag_dims.values())
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
