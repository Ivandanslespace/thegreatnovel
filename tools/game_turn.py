#!/usr/bin/env python3
"""统一回合入口：三阶段结构（第十九轮对话改进）

阶段一 resolve: 
  1. 推进同批玩家群体 → 2. 推进市场和排行榜 → 3. 执行主角行动 →  
  4. 计算同类玩家基准 → 5. 计算主角本轮分位 → 6. 生成公共系统反馈 →  
  7. OptionDirector 生成战略候选 → 8. Python 预检并保存三个行动合同 →  
  9. 返回 NarrativePackage（含 peer_comparison、ranking_changes、announcements 等）

阶段二 record: 校验小说文本 → 记录审计日志

用法：
    # 阶段一：结算（玩家选择选项）
    python tools/game_turn.py saves/世界名 resolve --player-choice A \
      --player-input '我选 A。'

    # 阶段一：结算（自由输入）
    python tools/game_turn.py saves/世界名 resolve \
      --action-json '{"action_id":"x","type":"EXPLORATION","target":"y"}' \
      --player-input '我去探索。'

    # 阶段一：仅生成选项（开局/选项过期）
    python tools/game_turn.py saves/世界名 resolve --generate-options-only

    # 阶段二：记录叙述（LLM 写完小说后调用）
    python tools/game_turn.py saves/世界名 record \
      --player-input '我选 A。' --gm-response-file response.md

输出：JSON NarrativePackage。LLM 只需把包写成小说，然后调用 record。
包含：
- status_panel / scene_context（原有）
- peer_comparison（新增）: 主角相对于同类玩家的百分位
- regional_statistics（新增）: 区域统计摘要
- ranking_changes（新增）: 排行榜变动列表
- system_announcements（新增）: 系统公告列表
- channel_feed（新增）: 频道消息摘要
- market_changes（新增）: 市场价格波动
- achievement_unlocks（新增）: 新解锁成就
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine_runtime.events import TIME_PERIOD_STARTS
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.presentation import player_facing_result
from engine_runtime.runtime import GameEngine
from engine_runtime.state import load_game_state
from engine_runtime.calculators import (
    calculate_peer_performance,
    calculate_comparative_result,
    simulate_peer_population_advancement,
)
from tools.validate_save import assert_startable

# ─── Perspective Cutaway Integration ───
from engine_runtime.perspective_director import PerspectiveDirector

FORBIDDEN_TERMS = [
    "预览合法", "未结算", "Python", "SQLite", "dry-run", "action_id", "确认执行", "compile_options", "preview",
    # New: prevent perspective system leakage
    "perspective_director", "convergence_score", "reader_knowledge",
    "thread_id", "PERSPECTIVE_CUTAWAY", "active_perspective_thread",
    "cutaway_contexts",
]
MAX_VISIBLE_OPTIONS = 3


def build_public_system_feedback(engine: GameEngine, turn: int) -> dict:
    """生成公共系统反馈信息（排行榜、公告、频道、市场）。"""
    state = engine.state
    world = state.data.get("world", {}) if isinstance(state.data.get("world", {}), dict) else {}
    meta = state.meta
    
    # 获取区域信息
    region_info = {
        "region_id": meta.get("region_id", "default"),
        "population_count": world.get("genre_contract", {}).get("region_size", 1000),
        "current_phase": meta.get("game_day", 1) <= 3 and "newbie_protection" or 
                        meta.get("game_day", 1) <= 10 and "early_game" or "mid_game",
    }
    
    # 模拟普通玩家进展
    population_resolution = simulate_peer_population_advancement(region_info, turn)
    
    # 生成系统公告（示例逻辑，实际应从事件历史中查询）
    announcements = []
    rankings = []
    
    # 检查是否有首杀/首建成就
    achievements = []
    
    return {
        "population_resolution": population_resolution,
        "announcements": announcements,
        "ranking_changes": rankings,
        "channel_messages": [],  # 从频道表查询
        "market_changes": [],    # 从市场快照查询
        "achievements": achievements,
        "regional_statistics": {
            "region_id": region_info["region_id"],
            "total_players": population_resolution["population_before"],
            "alive_after_turn": population_resolution["population_after"],
            "deaths_this_turn": population_resolution["deaths"],
            "achievements_unlocked": population_resolution["achievements_unlocked"],
        },
    }


def calculate_protagonist_comparison(engine: GameEngine, resolution_result: dict) -> dict:
    """计算主角相对于同类玩家的百分位。"""
    state = engine.state
    
    # 收集主角本次表现的各项指标
    action_quality_score = resolution_result.get("gain", {}).get("total_value", 50.0)
    resource_efficiency = resolution_result.get("resource_ratio", 1.0)
    permanent_growth = len(resolution_result.get("permanent_additions", [])) * 20.0
    risk_control_score = 100.0 if not resolution_result.get("injuries", []) else 50.0
    social_influence = len(resolution_result.get("social_impacts", [])) * 15.0
    
    player_stats = {
        "action_quality_score": action_quality_score,
        "resource_efficiency_ratio": resource_efficiency,
        "permanent_growth_value": permanent_growth,
        "risk_control_score": risk_control_score,
        "social_influence_points": social_influence,
    }
    
    performance_score = calculate_peer_performance(player_stats)
    
    # 获取普通玩家分布
    genre_contract = state.data.get("world", {}).get("genre_contract", {})
    difficulty_calibration = genre_contract.get("difficulty_calibration", {})
    
    # 构建默认的普通玩家分布（可根据阶段调整）
    phase = "newbie_protection"
    peer_distribution = {
        10: 32.0,
        25: 41.0,
        50: 50.0,
        75: 60.0,
        90: 70.0,
    }
    
    comparative_result = calculate_comparative_result(
        protagonist_performance=performance_score,
        peer_distribution=peer_distribution,
        matched_peer_count=200,
    )
    
    return {
        "protagonist_action_id": resolution_result.get("action_id", ""),
        "performance_score": performance_score,
        "percentile": comparative_result["percentile"],
        "power_percentile": comparative_result["percentile"],  # 简化处理
        "resource_percentile": comparative_result["percentile"],  # 简化处理
        "comparative_result": comparative_result["comparative_result"],
        "main_causes": [
            "high_risk_exploration_success",
            "efficient_extraction",
        ],
    }


def generate_strategic_candidates(engine: GameEngine) -> list[dict]:
    """从战略角度生成选项导演候选（外部推进/长期发展/社会博弈/生存管理）。"""
    state = engine.state
    world = state.data.get("world", {}) if isinstance(state.data.get("world", {}), dict) else {}
    meta = state.meta
    
    candidates = []
    current_location = engine._current_location()
    base_location = engine._base_location()
    available_time = float(meta.get("available_time_minutes", 720))
    time_of_day = str(meta.get("time_of_day", "清晨"))
    fatigue = float(state.player.get("fatigue", 0))
    
    # 类型合同定义
    genre_contract = world.get("genre_contract", {})
    has_public_system = genre_contract.get("public_system", {})
    
    # 1. 外部推进选项（探索/投放/副本/风险机会）
    action_targets = world.get("action_targets", {}) if isinstance(world.get("action_targets", {}), dict) else {}
    for target_id, profile in action_targets.items():
        if not isinstance(profile, dict):
            continue
        location_id = str(profile.get("location_id", ""))
        if location_id != current_location:
            continue
        constraints = profile.get("constraints", {}) if isinstance(profile.get("constraints", {}), dict) else {}
        availability = constraints.get("availability", {}) if isinstance(constraints.get("availability", {}), dict) else {}
        allowed_periods = availability.get("allowed_periods", [])
        
        if allowed_periods and time_of_day not in [str(p) for p in allowed_periods]:
            continue
        
        label = str(profile.get("label") or profile.get("name") or target_id)
        goal = str(profile.get("goal") or label)
        
        candidates.append({
            "category": "external_progress",
            "label": label,
            "description": goal,
            "action": {"action_id": f"strategic-{target_id}", "type": profile.get("action_type", "EXPLORATION"), "target": target_id},
        })
    
    # 2. 长期发展选项（建设/升级/制作/投资）
    if current_location == base_location and available_time >= 60:
        build_catalog = world.get("build_catalog", {}) if isinstance(world.get("build_catalog", {}), dict) else {}
        modules = list(build_catalog.values())[:2]
        for module in modules:
            if isinstance(module, dict):
                candidates.append({
                    "category": "long_term_development",
                    "label": f"建造{module.get('name', '')}",
                    "description": f"{module.get('description', '')}",
                    "action": {"action_id": f"build-{module.get('id', '')}", "type": "BUILD", "target": module.get("id", "")},
                })
    
    # 添加基础制作选项
    recipes = world.get("recipes", [])
    if isinstance(recipes, list) and len(recipes) > 0:
        recipe = recipes[0]
        candidates.append({
            "category": "long_term_development",
            "label": f"制作{recipe.get('name', '物品')}",
            "description": f"消耗{recipe.get('cost', {})}，耗时{recipe.get('time_minutes', 30)}分钟",
            "action": {"action_id": f"craft-{recipe.get('id', '')}", "type": "CRAFTING", "target": recipe.get("id", "")},
        })
    
    # 3. 玩家社会选项（交易/组队/竞争/信息博弈）
    if has_public_system.get("trading", False):
        candidates.append({
            "category": "player_social",
            "label": "浏览交易市场",
            "description": "查看当前区域的交易订单和市场行情",
            "action": {"action_id": "browse_market", "type": "VIEW_MARKET"},
        })
    
    if has_public_system.get("regional_chat", False):
        candidates.append({
            "category": "player_social",
            "label": "查看区域频道",
            "description": "浏览其他求生者的交流和情报分享",
            "action": {"action_id": "view_regional_channel", "type": "VIEW_CHANNEL", "parameters": {"channel": "regional"}},
        })
    
    if has_public_system.get("rankings", False):
        candidates.append({
            "category": "player_social",
            "label": "查看排行榜",
            "description": "了解自己在区域内的排名和领先程度",
            "action": {"action_id": "view_rankings", "type": "VIEW_RANKINGS"},
        })
    
    # 4. 生存管理选项（只有在真正需要时才展示）
    rest_thresholds_met = (
        fatigue >= 30 or
        float(state.player.get("mental", 100)) <= 65 or
        float(state.player.get("hp", 0)) / max(float(state.player.get("max_hp", 1)), 1) <= 0.85 or
        time_of_day in ["黄昏", "夜晚"]
    )
    
    if current_location == base_location and rest_thresholds_met and available_time >= 360:
        candidates.append({
            "category": "survival_management",
            "label": "完整休息恢复",
            "description": "休息约 6 小时，大幅恢复体力和精神",
            "action": {"action_id": "full-rest", "type": "REST", "target": base_location, "parameters": {"duration_minutes": 360}},
        })
    
    # 5. 自由行动提示
    candidates.append({
        "category": "free_action",
        "label": "自由行动",
        "description": "描述你想做的任何事，系统会结算后果",
        "action": {"action_id": "free-action", "type": "FREE_ACTION"},
    })
    
    # 确保至少有一个外部推进选项
    external_count = sum(1 for c in candidates if c["category"] == "external_progress")
    if external_count == 0 and action_targets:
        for target_id, profile in list(action_targets.items())[:1]:
            if isinstance(profile, dict) and profile.get("location_id") == current_location:
                candidates.insert(0, {
                    "category": "external_progress",
                    "label": str(profile.get("name", target_id)),
                    "description": str(profile.get("goal", "探索该地点")),
                    "action": {"action_id": f"forced-external-{target_id}", "type": profile.get("action_type", "EXPLORATION"), "target": target_id},
                })
    
    # 去重并限制数量
    seen_labels = set()
    unique_candidates = []
    for candidate in candidates:
        label = candidate["label"]
        if label not in seen_labels:
            seen_labels.add(label)
            unique_candidates.append(candidate)
    
    return unique_candidates[:MAX_VISIBLE_OPTIONS + 2]


def build_status_panel(engine: GameEngine) -> dict:
    player = engine.state.player
    meta = engine.state.meta
    attributes = player.get("attributes", {})
    return {
        "level": player.get("level", 1),
        "exp": player.get("exp", 0),
        "exp_to_next": player.get("exp_to_next", 100),
        "attributes": {
            "strength": attributes.get("strength", 0),
            "constitution": attributes.get("constitution", 0),
            "agility": attributes.get("agility", 0),
            "spirit": attributes.get("spirit", 0),
        },
        "hp": player.get("hp", 0),
        "max_hp": player.get("max_hp", 0),
        "fatigue": player.get("fatigue", 0),
        "mental": player.get("mental", 100),
        "status": player.get("status", "normal"),
        "game_day": meta.get("game_day", 1),
        "time_of_day": meta.get("time_of_day", "清晨"),
        "current_location": meta.get("current_location", ""),
        "available_time_minutes": meta.get("available_time_minutes", 720),
        "free_points": player.get("free_points", 0),
    }


def build_scene_context(engine: GameEngine) -> dict:
    meta = engine.state.meta
    world = engine.state.data.get("world", {})
    current_location = meta.get("current_location", "")
    locations = world.get("locations", []) if isinstance(world.get("locations", []), list) else []
    location_info = next((loc for loc in locations if isinstance(loc, dict) and loc.get("id") == current_location), {})
    npcs_here = [
        {"id": npc.get("id"), "name": npc.get("name"), "status": npc.get("status", "alive")}
        for npc in engine.state.data.get("npcs", [])
        if isinstance(npc, dict) and npc.get("location") == current_location and npc.get("status", "alive") == "alive"
    ]
    return {
        "location_id": current_location,
        "location_name": location_info.get("name", current_location),
        "location_safe": location_info.get("safe", False),
        "time_of_day": meta.get("time_of_day", "清晨"),
        "game_day": meta.get("game_day", 1),
        "npcs_present": npcs_here,
        "current_encounter_id": meta.get("current_encounter_id"),
        "pending_reaction": meta.get("pending_reaction"),
    }


def infer_action_type(profile: dict) -> str | None:
    """从目标配置推断正确的行动类型。"""
    explicit = profile.get("action_type")
    if explicit:
        return str(explicit)
    target_id = str(profile.get("id", ""))
    if target_id.startswith("npc_") or profile.get("is_npc"):
        return "SOCIAL_INTERACTION"
    if profile.get("encounter_target_ids"):
        return "EXPLORATION"
    effects = profile.get("effects", {})
    if isinstance(effects, dict):
        success = effects.get("success", {})
        if isinstance(success, dict) and success.get("knowledge_additions") and not success.get("resource_changes"):
            return "RESEARCH"
    if profile.get("target_difficulty", 0) == 0 and not effects:
        return None
    return "EXPLORATION"


def minutes_until_period(current_elapsed: float, target_period: str) -> float:
    """计算从当前 elapsed 到目标时段开始需要多少分钟。"""
    target_start = TIME_PERIOD_STARTS.get(target_period, 0)
    if target_start > current_elapsed:
        return target_start - current_elapsed
    return (720 - current_elapsed) + target_start


def generate_smart_candidates(engine: GameEngine) -> list[dict]:
    """从世界注册表生成智能候选：正确类型、过滤未发现、生成WAIT计划、限制数量。"""
    candidates: list[dict] = []
    current_location = engine._current_location()
    base_location = engine._base_location()
    world = engine.state.data.get("world", {}) if isinstance(engine.state.data.get("world", {}), dict) else {}
    action_targets = world.get("action_targets", {}) if isinstance(world.get("action_targets", {}), dict) else {}
    time_of_day = str(engine.state.meta.get("time_of_day", "清晨"))
    day_elapsed = float(engine.state.meta.get("day_elapsed_minutes", 0))
    available_time = float(engine.state.meta.get("available_time_minutes", 720))
    player_known = set(engine.state.player.get("discovered_locations", []))
    player_known.update(engine.state.player.get("known_locations", []))
    player_known.add(base_location)
    player_known.add(current_location)

    period_locked: list[dict] = []

    for target_id, profile in action_targets.items():
        if not isinstance(profile, dict):
            continue
        location_id = str(profile.get("location_id", ""))
        if location_id != current_location:
            continue
        action_type = infer_action_type(profile)
        if not action_type:
            continue
        constraints = profile.get("constraints", {}) if isinstance(profile.get("constraints", {}), dict) else {}
        availability = constraints.get("availability", {}) if isinstance(constraints.get("availability", {}), dict) else {}
        allowed_periods = availability.get("allowed_periods", [])
        label = str(profile.get("label") or profile.get("name") or "")
        if not label:
            if action_type == "SOCIAL_INTERACTION":
                npc_name = next(
                    (n.get("name", target_id) for n in engine.state.data.get("npcs", []) if isinstance(n, dict) and n.get("id") == target_id),
                    target_id,
                )
                label = f"与{npc_name}交谈"
            else:
                label = target_id

        if allowed_periods and time_of_day not in {str(p) for p in allowed_periods}:
            period_locked.append({"target_id": target_id, "profile": profile, "action_type": action_type, "allowed_periods": allowed_periods, "label": label})
            continue

        candidates.append({
            "label": label,
            "action": {"action_id": f"auto-{target_id}", "type": action_type, "target": target_id, "goal": str(profile.get("goal") or label)},
        })

    for locked in period_locked:
        best_wait = None
        for period in locked["allowed_periods"]:
            wait = minutes_until_period(day_elapsed, str(period))
            if best_wait is None or wait < best_wait:
                best_wait = wait
        if best_wait is not None and best_wait + 120 <= available_time and best_wait > 0:
            candidates.append({
                "label": f"等待至{locked['allowed_periods'][0]}并{locked['label']}",
                "action": {
                    "action_id": f"auto-wait-{locked['target_id']}",
                    "type": "ACTION_PLAN",
                    "plan_id": f"auto-wait-{locked['target_id']}",
                    "accept_dilution": True,
                    "steps": [
                        {"action_id": f"wait-step", "type": "WAIT", "parameters": {"wait_minutes": int(best_wait)}, "goal": f"等待进入{locked['allowed_periods'][0]}"},
                        {"action_id": f"action-step", "type": locked["action_type"], "target": locked["target_id"], "goal": locked["label"]},
                    ],
                },
            })

    if current_location != base_location:
        candidates.append({"label": "返回基地", "action": {"action_id": "auto-return", "type": "RETURN_TO_BASE"}})
    if current_location == base_location and available_time >= 360:
        candidates.append({"label": "休息恢复", "action": {"action_id": "auto-rest", "type": "REST", "target": base_location}})

    locations = world.get("locations", []) if isinstance(world.get("locations", []), list) else []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        loc_id = str(loc.get("id", ""))
        if loc_id == current_location or not loc_id:
            continue
        if loc_id == base_location:
            continue
        if loc_id not in player_known and loc.get("discovered") is False:
            continue
        candidates.append({"label": f"前往{loc.get('name', loc_id)}", "action": {"action_id": f"auto-travel-{loc_id}", "type": "TRAVEL", "target": loc_id}})

    return candidates[:MAX_VISIBLE_OPTIONS + 2]


def add_fallback_candidates(engine: GameEngine, candidates: list[dict]) -> list[dict]:
    """当候选不足时添加保底行动。"""
    current_location = engine._current_location()
    base_location = engine._base_location()
    available_time = float(engine.state.meta.get("available_time_minutes", 720))
    if not candidates:
        if current_location != base_location:
            candidates.append({"label": "返回基地", "action": {"action_id": "fallback-return", "type": "RETURN_TO_BASE"}})
        if available_time >= 5:
            candidates.append({"label": "等待", "action": {"action_id": "fallback-wait", "type": "WAIT", "parameters": {"wait_minutes": 30}, "goal": "观察周围"}})
        if current_location == base_location and available_time >= 360:
            candidates.append({"label": "休息", "action": {"action_id": "fallback-rest", "type": "REST", "target": base_location}})
    return candidates


def resolve_phase(engine: GameEngine, args) -> dict:
    """阶段一：三流程（群体推进→主角行动→公共反馈）+ 选项生成。"""
    state = engine.state
    turn = state.current_turn
    
    execution_result = None
    errors = []
    
    # 执行玩家行动或仅生成选项
    if not args.generate_options_only:
        if args.player_choice:
            execution_result = engine.execute_player_choice(args.player_choice.strip())
        elif args.action_json:
            action = json.loads(args.action_json)
            execution_result = engine.execute_host_action(action)
        else:
            return {"error": "必须提供 --player-choice、--action-json 或 --generate-options-only"}
    
    # 1. 推进同批玩家群体和市场
    public_feedback = build_public_system_feedback(engine, turn)
    
    # 2. 如果执行了行动，计算比较结果
    comparative_result = None
    if execution_result and isinstance(execution_result, dict):
        comparative_result = calculate_protagonist_comparison(engine, execution_result)
        public_feedback.setdefault("comparative_snapshot", comparative_result)
    
    # ─── EventDirector 异变事件注入（可选层，无 creative_slots 时完全跳过）───
    event_candidates = []
    if engine.state.data.get("world", {}).get("creative_slots"):
        from engine_runtime.event_director import EventDirector
        director = EventDirector(engine)
        event_candidates = director.evaluate_turn()

    # ─── Perspective Cutaway Injection (~5ms budget) ───
    perspective_cutaway = None
    try:
        director = PerspectiveDirector(engine)
        
        if director.should_trigger(turn):
            candidates = director.evaluate_candidates()
            if candidates and candidates[0].convergence_score >= 0.75:
                best = candidates[0]
                cutaway_package = director.generate_cutaway_package(best)
                
                # Convert to dict for NarrativePackage
                perspective_cutaway = {
                    "id": cutaway_package["id"],
                    "viewpoint_actor": best.peer_name,
                    "narrative_function": cutaway_package["narrative_function"],
                    "convergence_score": best.convergence_score,
                    "location_name": best.location_name,
                    "motivation": best.motivation,
                }
    except Exception as exc:
        # Fail silently: cutaway is optional, don't block main pipeline
        pass

    # 3. 生成战略候选（外部推进/长期发展/社会博弈）
    strategic_candidates = generate_strategic_candidates(engine)
    all_candidates = event_candidates + strategic_candidates
    
    # 4. 编译选项并保存合同
    options_status = "ok"
    visible_options = {}
    option_labels = {}
    
    if all_candidates:
        try:
            for candidate in all_candidates[:MAX_VISIBLE_OPTIONS + 1]:
                engine.compile_option(candidate["action"], persist=True)
            # 从 meta 中读取已保存的选项
            pending = state.meta.get("pending_options", {})
            if isinstance(pending, dict) and pending.get("options"):
                for key, option in list(pending["options"].items())[:MAX_VISIBLE_OPTIONS]:
                    if isinstance(option, dict):
                        visible_options[key] = {
                            "label": option.get("label", ""),
                            "description": option.get("description", ""),
                            "category": option.get("category", ""),
                        }
                        option_labels[key] = option.get("label", "")
        except ValueError as exc:
            options_status = "NEEDS_FALLBACK_OPTIONS"
            errors.append(f"选项编译失败：{exc}")
    else:
        options_status = "NEEDS_FALLBACK_OPTIONS"
        errors.append("无可用战略候选")
    
    # 5. 组装 NarrativePackage（包含新增的全民系统字段）
    package = {
        "phase": "resolve",
        "turn": turn,
        "options_status": options_status,
        "status_panel": build_status_panel(engine),
        "scene_context": build_scene_context(engine),
        "visible_options": visible_options,
        "option_labels": option_labels,
        "peer_comparison": comparative_result or {
            "protagonist_action_id": "none",
            "percentile": 50,
            "comparative_result": "not_calculated",
        },
        "regional_statistics": public_feedback.get("regional_statistics", {}),
        "system_announcements": public_feedback.get("announcements", []),
        "ranking_changes": public_feedback.get("ranking_changes", []),
        "channel_feed": public_feedback.get("channel_messages", []),
        "market_changes": public_feedback.get("market_changes", []),
        "achievement_unlocks": public_feedback.get("achievements", []),
        "free_action_available": True,
        "perspective_cutaway": perspective_cutaway,  # NEW - perspective cutaway fragment
    }
    
    if errors:
        package["errors"] = errors
    
    return package


def record_phase(engine: GameEngine, save_dir: Path, args) -> dict:
    """阶段二：校验小说文本 + 记录审计日志（含全民系统字段校验）。"""
    if not args.gm_response_file:
        return {"error": "record 阶段需要 --gm-response-file"}
    gm_path = Path(args.gm_response_file)
    if not gm_path.is_file():
        return {"error": f"GM 回答文件不存在：{gm_path}"}
    gm_text = gm_path.read_text(encoding="utf-8")
    
    violations = [term for term in FORBIDDEN_TERMS if term in gm_text]
    
    # 检查选项标签是否展示
    pending = engine.state.meta.get("pending_options", {})
    if isinstance(pending, dict) and pending.get("options"):
        for key, option in pending["options"].items():
            if isinstance(option, dict) and option.get("label"):
                if str(option["label"]) not in gm_text and key not in gm_text:
                    violations.append(f"选项{key}标签未在叙述中展示")
    
    # 校验全民系统反馈是否在小说中体现
    package_data = getattr(engine, "_last_package", None)
    if package_data:
        if package_data.get("peer_comparison", {}).get("percentile", 0) != 50:
            percentile = package_data["peer_comparison"]["percentile"]
            if f"前{int(100-percentile)}%" not in gm_text and f"超过{int(percentile)}%" not in gm_text:
                violations.append("百分位数据未在小说叙述中体现")
        
        announcements = package_data.get("system_announcements", [])
        if announcements and "系统公告" not in gm_text:
            violations.append("系统公告未展示给玩家")
    
    if violations:
        return {"status": "VALIDATION_FAILED", "violations": violations, "recorded": False}
    
    if args.player_input:
        record_narrative_turn(
            save_dir,
            args.player_input,
            gm_text,
            action=None,
            before_state=None,
            result=None,
        )
    
    return {"status": "recorded", "violations": [], "recorded": True}


def main():
    # 本文件保留为历史原型和纯函数参考。它曾自行推进群体、市场、事件导演
    # 并直接拼接候选，绕过唯一的合同编译/事件提交入口；继续作为 CLI 运行会
    # 产生无法重放的状态。正式游戏只允许 tools/turn_controller.py。
    print(json.dumps({
        "error": "LEGACY_ENTRYPOINT_DISABLED",
        "message": "game_turn.py 已停用；请使用 python tools/turn_controller.py。",
    }, ensure_ascii=False))
    sys.exit(2)

    parser = argparse.ArgumentParser(description="统一回合入口（三阶段，第十九轮对话改进版）")
    parser.add_argument("save_dir", type=str)
    parser.add_argument("phase", choices=["resolve", "record"], help="阶段：resolve=结算，record=记录叙述")
    parser.add_argument("--player-choice", type=str)
    parser.add_argument("--action-json", type=str)
    parser.add_argument("--player-input", type=str, default="")
    parser.add_argument("--gm-response-file", type=str)
    parser.add_argument("--generate-options-only", action="store_true")
    args = parser.parse_args()
    
    save_dir = Path(args.save_dir)
    if not save_dir.is_dir():
        print(json.dumps({"error": f"存档目录不存在：{save_dir}"}, ensure_ascii=False))
        sys.exit(1)
    
    assert_startable(save_dir)
    state = load_game_state(save_dir)
    engine = GameEngine(state)
    
    if args.phase == "resolve":
        result = resolve_phase(engine, args)
        engine._last_package = result  # 保存最后一轮包用于校验
    else:
        result = record_phase(engine, save_dir, args)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
