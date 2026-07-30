"""Turn Controller：统一回合控制器。

玩家发送消息后，LLM 只需调用这一个入口。控制器自动：
1. 识别输入类型（选项 A/B/C 或自由行动）
2. 执行 Python 规则结算
3. 生成下一回合合法选项
4. 返回 NarrativePackage（LLM 只需写成小说）

用法：
    # 玩家选择选项（无需 LLM 解析意图）
    python tools/turn_controller.py saves/世界名 --player-input "A"

    # 玩家自由输入（LLM 提供轻量意图解析）
    python tools/turn_controller.py saves/世界名 \
      --player-input "我先检查车厢，然后问阿苔供水情况" \
      --action-json '{"action_id":"plan-1","type":"ACTION_PLAN",...}'

    # 仅生成选项（开局/选项过期/需要刷新）
    python tools/turn_controller.py saves/世界名 --generate-options-only

    # 记录叙述（LLM 写完小说后调用）
    python tools/turn_controller.py saves/世界名 record \
      --turn-token "turn-13-a1b2c3" --response-file response.md

输出：JSON NarrativePackage。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine_runtime.events import TIME_PERIOD_STARTS, standard_event
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.presentation import player_facing_result
from engine_runtime.public_survival import advance_public_states, public_snapshot
from engine_runtime.runtime import GameEngine
from engine_runtime.state import load_game_state
from tools.validate_save import assert_startable

FORBIDDEN_TERMS = [
    "预览合法", "未结算", "Python", "SQLite", "dry-run",
    "action_id", "确认执行", "compile_options", "preview",
]
MAX_VISIBLE_OPTIONS = 3

# 匹配纯选项输入：A / B / C / a / b / c / 选A / 我选B / "A" 等
OPTION_PATTERN = re.compile(
    r'^\s*["\']?([A-Ca-c])["\']?\s*$'
    r'|^\s*(?:我)?选\s*([A-Ca-c])\s*$'
    r'|^\s*(?:option|选)\s*([A-Ca-c])\s*$',
    re.IGNORECASE,
)


def _make_turn_token(turn: int) -> str:
    """生成回合令牌，用于 record 阶段校验。"""
    raw = f"turn-{turn}-{time.time_ns()}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"turn-{turn}-{digest}"


def _parse_option_input(text: str) -> str | None:
    """检测玩家输入是否为选项选择，返回选项 ID 或 None。"""
    text = text.strip()
    match = OPTION_PATTERN.match(text)
    if match:
        for group in match.groups():
            if group:
                return group.upper()
    return None


# ─── 状态面板与场景上下文 ───────────────────────────────────────────


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


def build_opening_contract(engine: GameEngine) -> dict:
    """交给主持器的开局事实：规则、天赋卡与公共求生界面。"""
    world = engine.state.data.get("world", {}) if isinstance(engine.state.data.get("world", {}), dict) else {}
    talent = engine.state.data.get("player_talent", {}) if isinstance(engine.state.data.get("player_talent", {}), dict) else {}
    rules = world.get("rules", {}) if isinstance(world.get("rules", {}), dict) else {}
    return {
        "world_rules": {
            "exploration": rules.get("exploration", {}),
            "death": rules.get("death", {}),
            "disaster": rules.get("disaster", {}),
        },
        "protagonist_talent_card": {
            "name": talent.get("name", ""),
            "description": talent.get("description", ""),
            "trigger": talent.get("trigger", ""),
            "effect": talent.get("effect", ""),
            "opening_card": talent.get("opening_card", {}),
        },
        "public_survival": public_snapshot(engine.state.data),
    }


def _has_time_advancing_result(result: dict | None) -> bool:
    """零时间的属性/天赋选择不推进同区玩家，真正行动才会。"""
    if not isinstance(result, dict):
        return False
    events = []
    event = result.get("event")
    if isinstance(event, dict):
        events.append(event)
    events.extend(item for item in result.get("events", []) if isinstance(item, dict))
    for record in events:
        payload = record.get("data", {}) if isinstance(record.get("data", {}), dict) else {}
        if float(payload.get("time_cost", 0) or 0) > 0:
            return True
    return False


def advance_public_system(engine: GameEngine, execution_result: dict | None) -> dict | None:
    """经由标准事件提交公共推进；不直接写入投影文件。"""
    if not _has_time_advancing_result(execution_result):
        return None
    advanced = advance_public_states(engine.state.data, execution_result or {})
    if advanced is None:
        return None
    projection_state, feedback = advanced
    turn = engine.state.current_turn
    record = standard_event(
        event_id=f"evt_{turn:04d}_public",
        event_type="PUBLIC_SYSTEM_ADVANCED",
        actor="system",
        target=None,
        data={"projection_state": projection_state, "public_feedback": feedback},
        turn=turn,
        timestamp=f"Day {engine.state.meta.get('game_day', 1)} {engine.state.meta.get('time_of_day', '清晨')}",
    )
    engine.state.apply_and_append(record, persist=True)
    engine.state.save()
    return feedback


# ─── 智能候选生成 ───────────────────────────────────────────────────


def _generate_npc_topics(engine: GameEngine) -> list[dict]:
    """生成 NPC 具体对话话题（P0-4）。"""
    topics = []
    current_location = engine._current_location()
    
    # P0-4: 从 state.data.npcs 而不是 world.npcs 获取 NPC 列表
    npcs = engine.state.data.get("npcs", []) if isinstance(engine.state.data, dict) else []
    
    # 找到当前 NPC（目前只有阿苔）
    npc = next((n for n in npcs if isinstance(n, dict) and n.get("id") == "npc_atai" and n.get("location") == current_location), None)
    if not npc:
        return topics
    
    player = engine.state.player
    knowledge = set(player.get("knowledge", []))
    
    # P0-4: 所有话题都有前置条件和一次性奖励
    topic_definitions = [
        {
            "id": "ask-route-plan",
            "label": "询问下一次停靠路线",
            "description": "了解列车即将停泊的位置和预计停留时间",
            "requirements": [],
            "cooldown_turns": 7,
            "last_used": -100,  # 假设很久没用了
            "effects": {
                "success": {"knowledge_additions": ["route_plan_day7"]}
            }
        },
        {
            "id": "help-water-system",
            "label": "协助检查供水管",
            "description": "和阿苔一起巡视列车净水循环系统",
            "requirements": ["has_basic_knowledge"],
            "cooldown_turns": 5,
            "last_used": -100,
            "effects": {
                "success": {
                    "relationship_changes": {"npc_atai": {"trust": 2, "respect": 1}},
                    "resource_changes": {"净水": 1}
                }
            }
        },
        {
            "id": "propose-search-natural-source",
            "label": "提出共同搜索净水源",
            "description": "建议离开列车寻找天然水源",
            "requirements": [],
            "cooldown_turns": 10,
            "last_used": -100,
            "effects": {
                "success": {"knowledge_additions": ["water_source_risk_assessment"]},
                "relationship_changes": {"npc_atai": {"trust": 3}}
            }
        },
        {
            "id": "ask-about-dagger-calluses",
            "label": "追问她手上的刀茧",
            "description": "观察并询问她手上的旧伤",
            "requirements": [],
            "cooldown_turns": 20,  # 很长，暗示很私密
            "last_used": -100,
            "effects": {
                "success": {
                    "knowledge_additions": ["atai_past_military_background"],
                    "relationship_changes": {"npc_atai": {"affection": 2, "intimacy": 1}}
                }
            }
        },
        {
            "id": "promise-scout-scrap-yard",
            "label": "向她承诺负责废铁站场侦察",
            "description": "主动承担探索废铁站场的责任",
            "requirements": ["npc_atai_goal"],
            "cooldown_turns": 14,
            "last_used": -100,
            "effects": {
                "success": {
                    "relationship_changes": {"npc_atai": {"trust": 5, "commitment": 3}},
                    "promise_additions": [{"npc_id": "npc_atai", "content": "确保废铁站场安全", "due_turn": "next_visit"}]
                }
            }
        }
    ]
    
    for topic in topic_definitions:
        topic_id = topic["id"]
        
        # 检查冷却
        turn_diff = engine.state.current_turn - topic.get("last_used", 0)
        if turn_diff < topic["cooldown_turns"]:
            continue
        
        # 检查前置条件
        requirements_met = all(req in knowledge or req.startswith("has_") for req in topic["requirements"])
        if not requirements_met:
            continue
        
        topics.append({
            "label": f"[对话] {topic['label']}",
            "action": {
                "action_id": f"auto-topic-{topic_id}",
                "type": "SOCIAL_INTERACTION",
                "target": "npc_atai",
                "goal": topic["label"],
                "parameters": {"topic": topic_id}
            },
            "priority_category": "social_development",
            "tags": ["conversation", f"topic:{topic_id}"]
        })
    
    return topics


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


def _area_enemy_level(area: dict) -> int:
    """从区域配置中提取最高敌人等级。"""
    max_level = 0
    for group in (area.get("enemy_groups") or []):
        if isinstance(group, dict):
            max_level = max(max_level, int(group.get("level", 0)))
    return max_level


def generate_smart_candidates(engine: GameEngine) -> list[dict]:
    """从世界注册表生成智能候选：正确类型、渐进发现、生成WAIT计划、基地建造。"""
    candidates: list[dict] = []
    pending_decision = engine.state.player.get("pending_decision", {})
    if isinstance(pending_decision, dict) and pending_decision.get("type") == "TALENT_CHOICE":
        # 升级三选一不是叙述建议，而是必须执行的已注册行动。先把它们编译为
        # 玩家可直接输入 A/B/C 的合同；属性点仍可由玩家的自由输入零时间分配。
        for option in pending_decision.get("options", []):
            if not isinstance(option, dict) or not option.get("id"):
                continue
            name = str(option.get("name", option["id"]))
            candidates.append({
                "label": f"觉醒天赋：{name}",
                "description": str(option.get("description", "")),
                "action": {
                    "action_id": f"auto-talent-{option['id']}",
                    "type": "TALENT_CHOICE",
                    "target": str(option["id"]),
                },
            })
        return candidates

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

    # 活动遭遇是一个封闭的风险状态：不能继续生成探索、建设或社交选项。
    # 无论撤离是否满足条件，始终给出离开遭遇这一保底出口，防止玩家被
    # 过期选项或时间窗锁死在地点中。
    active_encounter = engine._current_active_encounter()
    if active_encounter:
        encounter_candidates: list[dict] = []
        for target_id in active_encounter.get("target_ids", []) if isinstance(active_encounter.get("target_ids", []), list) else []:
            try:
                target = engine._lookup_target(target_id)
            except ValueError:
                # 损坏的历史遭遇不能反过来卡死回合；离开遭遇仍会由下方保留。
                continue
            if isinstance(target, dict) and target.get("status", "alive") not in {"dead", "destroyed"}:
                encounter_candidates.append({
                    "label": f"应战：{target.get('name', target_id)}",
                    "action": {"action_id": f"encounter-combat-{target_id}", "type": "COMBAT", "target": target_id},
                })
        encounter_candidates.extend([
            {"label": "撤回基地", "action": {"action_id": "encounter-extract", "type": "EXTRACT"}},
            {"label": "脱离当前遭遇", "action": {"action_id": "encounter-leave", "type": "LEAVE_ENCOUNTER"}},
        ])
        return balance_options_by_category(encounter_candidates, max_output=MAX_VISIBLE_OPTIONS)

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
                        {"action_id": "wait-step", "type": "WAIT", "parameters": {"wait_minutes": int(best_wait)}, "goal": f"等待进入{locked['allowed_periods'][0]}"},
                        {"action_id": "action-step", "type": locked["action_type"], "target": locked["target_id"], "goal": locked["label"]},
                    ],
                },
            })

    if current_location != base_location:
        candidates.append({"label": "返回基地", "action": {"action_id": "auto-return", "type": "RETURN_TO_BASE"}})
    
    # P0-3: REST 收益阈值 - 只在有效恢复≥15 时展示主要选项
    # 如果玩家已经接近满状态，不应让休息成为常规选择
    if current_location == base_location and available_time >= 360:
        player = engine.state.player
        fatigue = float(player.get("fatigue", 0))
        max_mental = float(player.get("max_mental", 100))
        mental = float(player.get("mental", 100))
        hp = float(player.get("hp", 50))
        max_hp = float(player.get("max_hp", 50))
        
        # 计算有效恢复量（受限于单次休息上限）
        effective_recovery = min(fatigue, 35) + min(max(0, max_mental - mental), 20) + min(max(0, max_hp - hp), 5)
        
        # 只有当有效恢复达到一定程度时，才作为主要候选展示
        # forced_sleep 条件：极度疲劳 (>90) 或 HP 低于 30%
        forced_sleep = (fatigue > 90) or (hp < max_hp * 0.3)
        
        if effective_recovery >= 15 or forced_sleep:
            candidates.append({
                "label": "休息恢复", 
                "action": {"action_id": "auto-rest", "type": "REST", "target": base_location}
            })
        else:
            # 低价值休息不添加，避免选项池被垃圾填塞
            pass

    # ── 渐进发现：按距离排序，只展示最近的未发现地点 ──
    # 玩家可以前往任何已注册地点，但选项面板只显示最近的几个未发现地点。
    # 已发现的地点始终显示。地点难度过高时暂时隐藏（防止新手闯入高等级区）。
    player_level = int(engine.state.player.get("level", 1))
    max_reachable_level = player_level + 3  # 允许看到比自己高3级的区域
    max_travel_shown = 2  # 最多同时展示2个旅行候选

    locations = world.get("locations", []) if isinstance(world.get("locations", []), list) else []
    areas = world.get("areas", {}) if isinstance(world.get("areas", {}), dict) else {}
    travel_candidates: list[tuple[float, dict]] = []

    for loc in locations:
        if not isinstance(loc, dict):
            continue
        loc_id = str(loc.get("id", ""))
        if loc_id == current_location or not loc_id:
            continue
        if loc_id == base_location:
            continue

        is_known = loc_id in player_known or loc.get("discovered") is True
        if not is_known:
            # 渐进发现：检查该区域敌人等级是否在可达范围
            area = areas.get(loc_id, {})
            if isinstance(area, dict) and area:
                enemy_level = _area_enemy_level(area)
                if enemy_level > 0 and enemy_level > max_reachable_level:
                    continue
            travel_candidates.append((float(loc.get("travel_minutes_from_base", 999)), {
                "label": f"前往{loc.get('name', loc_id)}",
                "action": {"action_id": f"auto-travel-{loc_id}", "type": "TRAVEL", "target": loc_id},
            }))
        else:
            # 已发现的地点始终可前往
            candidates.append({"label": f"前往{loc.get('name', loc_id)}", "action": {"action_id": f"auto-travel-{loc_id}", "type": "TRAVEL", "target": loc_id}})

    # 按距离排序，取最近的 max_travel_shown 个
    travel_candidates.sort(key=lambda pair: pair[0])
    for _, cand in travel_candidates[:max_travel_shown]:
        candidates.append(cand)

    # ── 基地建造：在基地时，提供 build_catalog 中的建造选项 ──
    if current_location == base_location:
        build_catalog = world.get("build_catalog", {}) if isinstance(world.get("build_catalog", {}), dict) else {}
        for build_id, build_info in build_catalog.items():
            if not isinstance(build_info, dict):
                continue
            # 跳过已建造的模块（避免重复选项）
            base_modules = engine.state.data.get("base", {}).get("modules", []) if isinstance(engine.state.data.get("base", {}), dict) else []
            already_built = any(
                isinstance(m, dict) and m.get("id") == build_id and m.get("status") == "built"
                for m in (base_modules if isinstance(base_modules, list) else [])
            )
            if already_built:
                continue
            build_name = str(build_info.get("name", build_id))
            candidates.append({
                "label": f"建造{build_name}",
                "action": {"action_id": f"auto-build-{build_id}", "type": "BUILD", "target": build_id},
            })

    # 对话、维护等候选必须来自 world.action_targets。此前的硬编码 NPC
    # 话题和“整理物资”没有注册状态效果，会制造无法结算的伪选项，故不再注入。

    # P0-5: 按类别平衡选择最终输出
    return balance_options_by_category(candidates, max_output=MAX_VISIBLE_OPTIONS)


# ─── Option Director: 类别平衡与价值评分 (P0-5) ───────────────────────────


def categorize_option(candidate: dict) -> str:
    """将行动分配到战略类别。"""
    action = candidate.get("action", {})
    action_type = str(action.get("type", ""))
    
    # P0-5: 明确分类
    if action_type in {"TRAVEL", "ENTER_LOCATION"}:
        return "exploration_travel"
    if action_type == "EXPLORATION":
        return "exploration_activity"
    if action_type in {"EXTRACT", "RETURN_TO_BASE"}:
        return "movement_safety"
    if action_type == "BUILD":
        return "base_development"
    if action_type == "BASE_MANAGEMENT":
        return "base_management"
    if action_type in {"SOCIAL_INTERACTION"}:
        return "relationship_development"
    if action_type == "COMBAT":
        return "combat_encounter"
    if action_type == "REST":
        return "rest_recovery"
    if action_type == "SHORT_ACTION":
        goal = str(action.get("goal", "")).lower()
        if "inspect" in goal or "check" in goal:
            return "maintenance_short"
        if "organize" in goal or "survey" in goal:
            return "base_management"
        return "miscellaneous"
    return "miscellaneous"


def score_option_category(category: str, candidate_pool: list[dict]) -> float:
    """计算该类别的补充价值分数（稀缺性越高分数越高）。"""
    count_in_pool = sum(1 for c in candidate_pool if categorize_option(c) == category)
    if count_in_pool >= 1:
        # 已有一个，降分
        return 0.3
    elif count_in_pool >= 2:
        # 已有两个，大幅下降
        return 0.1
    else:
        # 没有，加分
        return 1.0


def balance_options_by_category(candidates: list[dict], max_output: int = 3) -> list[dict]:
    """从候选池中按类别平衡选择最终选项（P0-5）。"""
    if len(candidates) <= max_output:
        return candidates
    
    # 分组
    by_category: dict[str, list[dict]] = {}
    for c in candidates:
        cat = categorize_option(c)
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(c)
    
    # 选择：每种类型优先选一个，直到满 3 个
    selected: list[dict] = []
    used_categories: set[str] = set()
    
    # 第一轮：每个类别选一个代表性选项
    for category, group in sorted(by_category.items(), key=lambda x: -score_option_category(x[0], candidates)):
        if len(selected) >= max_output:
            break
        
        # 简单策略：选第一个，或优先级最高的
        winner = group[0]
        selected.append(winner)
        used_categories.add(category)
    
    # 第二轮：如果还不足 3 个，从剩余类别补齐
    for category, group in sorted(by_category.items(), key=lambda x: x[0]):
        if len(selected) >= max_output:
            break
        if category not in used_categories:
            selected.append(group[0])
    
    return selected[:max_output]


def generate_merged_short_actions(engine: GameEngine) -> list[dict]:
    """生成合并后的短行动序列（P0-6 决策压缩）。"""
    candidates = []
    current_location = engine._current_location()
    base_location = engine._base_location()
    inventory = engine.state.inventory.get("resources", {}) if isinstance(engine.state.inventory, dict) else {}
    
    # 不在基地时不考虑合并活动
    if current_location != base_location:
        return candidates
    
    player = engine.state.player
    available_time = float(player.get("fatigue", 100)) < 30  # 精力较好
    
    if available_time and len(inventory) >= 3:
        # 检查背包/装备的多种维护行动
        candidates.append({
            "label": "为下一次停靠做准备",
            "action": {
                "action_id": "auto-merge-preparation",
                "type": "ACTION_PLAN",
                "plan_id": "prep-for-stop",
                "accept_dilution": False,
                "steps": [
                    {
                        "action_id": "step-inspect-gear",
                        "type": "SHORT_ACTION",
                        "target": current_location,
                        "goal": "检查武器和工具的耐久状况"
                    },
                    {
                        "action_id": "step-organize",
                        "type": "BASE_MANAGEMENT",
                        "target": current_location,
                        "goal": "清点和整理物资储备"
                    }
                ],
                "goal": "为下一次列车停靠做好综合准备"
            },
            "priority_category": "base_management"
        })
        
        # 询问 + 休息组合
        if player.get("fatigue", 0) > 20:
            candidates.append({
                "label": "问完阿苔就去补觉",
                "action": {
                    "action_id": "auto-merge-question-rest",
                    "type": "ACTION_PLAN",
                    "plan_id": "ask-and-rest",
                    "accept_dilution": True,
                    "steps": [
                        {
                            "action_id": "step-talk-atai",
                            "type": "SOCIAL_INTERACTION",
                            "target": "npc_atai",
                            "goal": "快速询问当前状况",
                            "parameters": {"topic": "status-check"}
                        },
                        {
                            "action_id": "step-rest",
                            "type": "REST",
                            "target": current_location,
                            "goal": "恢复体力"
                        }
                    ],
                    "goal": "先确认信息再休息恢复"
                },
                "priority_category": "social_recovery"
            })
    
    return candidates


def add_fallback_candidates(engine: GameEngine, candidates: list[dict]) -> list[dict]:
    """当候选不足时添加保底行动，包括环境观察和短行动。"""
    current_location = engine._current_location()
    base_location = engine._base_location()
    available_time = float(engine.state.meta.get("available_time_minutes", 720))
    if not candidates:
        if current_location != base_location:
            candidates.append({"label": "返回基地", "action": {"action_id": "fallback-return", "type": "RETURN_TO_BASE"}})
        if available_time >= 5:
            candidates.append({"label": "等待并观察变化", "action": {"action_id": "fallback-wait", "type": "WAIT", "parameters": {"wait_minutes": min(30, int(available_time))}, "goal": "等待局势或时段发生变化"}})
        if current_location == base_location and available_time >= 360:
            candidates.append({"label": "休息", "action": {"action_id": "fallback-rest", "type": "REST", "target": base_location}})
    return candidates


# ─── 核心：resolve 阶段 ─────────────────────────────────────────────


def resolve(engine: GameEngine, player_input: str, action_json: str | None = None, generate_options_only: bool = False) -> dict:
    """统一结算入口。

    路由逻辑：
    1. 检测 player_input 是否匹配 pending_options 中的选项 → 直接执行合同
    2. 如果提供了 action_json → 执行自由行动
    3. generate_options_only → 仅刷新选项
    """
    execution_result = None
    public_feedback = None
    errors: list[str] = []
    input_mode = "unknown"

    if generate_options_only:
        input_mode = "generate_options_only"
    else:
        # 路径一：检测是否为选项输入
        option_id = _parse_option_input(player_input)
        if option_id:
            input_mode = "player_choice"
            try:
                execution_result = engine.execute_player_choice(option_id)
            except ValueError as exc:
                return {"error": f"选项执行失败：{exc}", "input_mode": input_mode}
        elif action_json:
            # 路径二：自由行动（LLM 已解析意图）
            input_mode = "free_text"
            try:
                action = json.loads(action_json)
                execution_result = engine.execute_host_action(action)
            except (json.JSONDecodeError, ValueError) as exc:
                return {"error": f"自由行动执行失败：{exc}", "input_mode": input_mode}
        else:
            # 路径三：输入不是选项，也没有 action_json
            # 检查是否看起来像选项但不在 pending 中
            pending = engine.state.meta.get("pending_options", {})
            has_pending = isinstance(pending, dict) and bool(pending.get("options"))
            if has_pending:
                return {
                    "error": "NEEDS_INTENT_PARSE",
                    "message": "玩家输入不是已展示的选项，需要 LLM 解析为行动 JSON 后重新调用（附带 --action-json）",
                    "player_input": player_input,
                    "input_mode": "needs_parse",
                    "status_panel": build_status_panel(engine),
                    "scene_context": build_scene_context(engine),
                }
            else:
                return {
                    "error": "NO_PENDING_OPTIONS",
                    "message": "没有待执行选项。请使用 --generate-options-only 生成选项，或提供 --action-json",
                    "input_mode": "no_options",
                }

    public_feedback = advance_public_system(engine, execution_result)

    # 生成下一回合候选并编译
    candidates = generate_smart_candidates(engine)
    candidates = add_fallback_candidates(engine, candidates)

    options_status = "ok"
    if candidates:
        try:
            engine.compile_options(candidates[:MAX_VISIBLE_OPTIONS + 1], persist=True)
        except ValueError as exc:
            # 原候选可能都因库存、地点或一次性效果已完成而被过滤；此时
            # 不能把玩家留在无选项状态。等待是唯一不依赖外部对象的合法出口。
            available_time = float(engine.state.meta.get("available_time_minutes", 0))
            if available_time >= 5:
                fallback = [{
                    "label": "等待并观察变化",
                    "action": {
                        "action_id": "compile-fallback-wait",
                        "type": "WAIT",
                        "parameters": {"wait_minutes": min(30, int(available_time))},
                        "goal": "等待局势或时段发生变化",
                    },
                }]
                try:
                    engine.compile_options(fallback, persist=True)
                    errors.append(f"原候选不可执行，已改为时间推进：{exc}")
                except ValueError as fallback_exc:
                    options_status = "NEEDS_FALLBACK_OPTIONS"
                    errors.append(f"选项编译失败：{exc}；保底行动失败：{fallback_exc}")
            else:
                options_status = "NEEDS_FALLBACK_OPTIONS"
                errors.append(f"选项编译失败：{exc}")
    else:
        options_status = "NEEDS_FALLBACK_OPTIONS"
        errors.append("无可用候选行动")

    # 构建 NarrativePackage
    turn_token = _make_turn_token(engine.state.current_turn)
    package: dict = {
        "phase": "resolve",
        "turn_token": turn_token,
        "turn": engine.state.current_turn,
        "input_mode": input_mode,
        "options_status": options_status,
        "status_panel": build_status_panel(engine),
        "scene_context": build_scene_context(engine),
        "visible_options": {},
        "option_labels": {},
        "free_action_available": True,
        **build_opening_contract(engine),
    }
    if errors:
        package["errors"] = errors
    if execution_result:
        package["resolved"] = player_facing_result(execution_result)
    if public_feedback:
        package["public_feedback"] = public_feedback

    pending = engine.state.meta.get("pending_options", {})
    if isinstance(pending, dict) and pending.get("options"):
        for key, option in list(pending["options"].items())[:MAX_VISIBLE_OPTIONS]:
            if isinstance(option, dict):
                package["visible_options"][key] = {
                    "label": option.get("label", ""),
                    "description": option.get("description", ""),
                }
                package["option_labels"][key] = option.get("label", "")

    return package


# ─── 核心：record 阶段 ──────────────────────────────────────────────


def record(save_dir: Path, engine: GameEngine, turn_token: str, response_file: str, player_input: str) -> dict:
    """校验小说文本并记录审计日志。"""
    if not response_file:
        return {"error": "record 阶段需要 --response-file"}
    gm_path = Path(response_file)
    if not gm_path.is_file():
        return {"error": f"GM回答文件不存在：{gm_path}"}
    gm_text = gm_path.read_text(encoding="utf-8")

    # 校验禁止词
    violations = [term for term in FORBIDDEN_TERMS if term in gm_text]

    # 校验选项标签一致性
    pending = engine.state.meta.get("pending_options", {})
    if isinstance(pending, dict) and pending.get("options"):
        for key, option in pending["options"].items():
            if isinstance(option, dict) and option.get("label"):
                if str(option["label"]) not in gm_text and key not in gm_text:
                    violations.append(f"选项{key}标签未在叙述中展示")

    if violations:
        return {"status": "VALIDATION_FAILED", "violations": violations, "recorded": False}

    # 确定意图来源
    intent_source = "player_choice" if _parse_option_input(player_input) else "player_free_text"

    record_narrative_turn(
        save_dir,
        player_input,
        gm_text,
        action=None,
        before_state=None,
        result=None,
        intent_source=intent_source,
    )
    return {"status": "recorded", "turn_token": turn_token, "violations": [], "recorded": True}


# ─── CLI 入口 ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Turn Controller：统一回合控制器",
        epilog="LLM 只需调用此入口，不需要选择其他脚本。",
    )
    parser.add_argument("save_dir", type=str, help="存档目录路径")
    parser.add_argument("phase", nargs="?", default="resolve", choices=["resolve", "record"],
                        help="阶段：resolve=结算（默认）, record=记录叙述")

    # resolve 阶段参数
    parser.add_argument("--player-input", type=str, default="",
                        help="玩家原始输入（如 'A'、'我选B'、自由文本）")
    parser.add_argument("--action-json", type=str, default=None,
                        help="LLM 解析的行动 JSON（自由输入时必填）")
    parser.add_argument("--generate-options-only", action="store_true",
                        help="仅生成/刷新选项，不执行行动")

    # record 阶段参数
    parser.add_argument("--turn-token", type=str, default="",
                        help="resolve 返回的回合令牌")
    parser.add_argument("--response-file", type=str, default="",
                        help="LLM 生成的小说文件路径")

    args = parser.parse_args()

    save_dir = Path(args.save_dir)
    if not save_dir.is_dir():
        print(json.dumps({"error": f"存档目录不存在：{save_dir}"}, ensure_ascii=False))
        sys.exit(1)

    state = load_game_state(save_dir)
    # 旧存档若缺少后来加入的公共状态投影，先以可重放的系统事件迁移，
    # 再执行启动门禁，避免正确的存档被格式升级本身卡死。
    state.migrate_projection_schema()
    assert_startable(save_dir)
    engine = GameEngine(state)

    if args.phase == "resolve":
        result = resolve(engine, args.player_input, args.action_json, args.generate_options_only)
    else:
        result = record(save_dir, engine, args.turn_token, args.response_file, args.player_input)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
