"""统一回合入口：两阶段结构。

阶段一 resolve：执行行动 → 生成选项 → 返回 NarrativePackage
阶段二 record：校验小说文本 → 记录审计日志

用法：
    # 阶段一：结算（玩家选择选项）
    python tools/game_turn.py saves/世界名 resolve --player-choice A \
      --player-input '我选A。'

    # 阶段一：结算（自由输入）
    python tools/game_turn.py saves/世界名 resolve \
      --action-json '{"action_id":"x","type":"EXPLORATION","target":"y"}' \
      --player-input '我去探索。'

    # 阶段一：仅生成选项（开局/选项过期）
    python tools/game_turn.py saves/世界名 resolve --generate-options-only

    # 阶段二：记录叙述（LLM写完小说后调用）
    python tools/game_turn.py saves/世界名 record \
      --player-input '我选A。' --gm-response-file response.md

输出：JSON NarrativePackage。LLM 只需把包写成小说，然后调用 record。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine_runtime.events import TIME_PERIOD_STARTS
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.presentation import player_facing_result
from engine_runtime.runtime import GameEngine
from engine_runtime.state import load_game_state
from tools.validate_save import assert_startable

FORBIDDEN_TERMS = ["预览合法", "未结算", "Python", "SQLite", "dry-run", "action_id", "确认执行", "compile_options", "preview"]
MAX_VISIBLE_OPTIONS = 3


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
    player_known = set(engine.state.player.get("known_locations", []))
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
    """阶段一：执行行动 + 生成选项 + 返回 NarrativePackage。"""
    execution_result = None
    errors: list[str] = []

    if args.generate_options_only:
        pass
    elif args.player_choice:
        execution_result = engine.execute_player_choice(args.player_choice.strip())
    elif args.action_json:
        action = json.loads(args.action_json)
        execution_result = engine.execute_host_action(action)
    else:
        return {"error": "必须提供 --player-choice、--action-json 或 --generate-options-only"}

    candidates = generate_smart_candidates(engine)
    candidates = add_fallback_candidates(engine, candidates)

    options_status = "ok"
    if candidates:
        try:
            engine.compile_options(candidates[:MAX_VISIBLE_OPTIONS + 1], persist=True)
        except ValueError as exc:
            options_status = "NEEDS_FALLBACK_OPTIONS"
            errors.append(f"选项编译失败：{exc}")
    else:
        options_status = "NEEDS_FALLBACK_OPTIONS"
        errors.append("无可用候选行动")

    package: dict = {
        "phase": "resolve",
        "turn": engine.state.current_turn,
        "options_status": options_status,
        "status_panel": build_status_panel(engine),
        "scene_context": build_scene_context(engine),
        "visible_options": {},
        "option_labels": {},
    }
    if errors:
        package["errors"] = errors
    if execution_result:
        package["resolved"] = player_facing_result(execution_result)
    pending = engine.state.meta.get("pending_options", {})
    if isinstance(pending, dict) and pending.get("options"):
        for key, option in list(pending["options"].items())[:MAX_VISIBLE_OPTIONS]:
            if isinstance(option, dict):
                package["visible_options"][key] = {"label": option.get("label", ""), "description": option.get("description", "")}
                package["option_labels"][key] = option.get("label", "")
    package["free_action_available"] = True
    return package


def record_phase(engine: GameEngine, save_dir: Path, args) -> dict:
    """阶段二：校验小说文本 + 记录审计日志。"""
    if not args.gm_response_file:
        return {"error": "record 阶段需要 --gm-response-file"}
    gm_path = Path(args.gm_response_file)
    if not gm_path.is_file():
        return {"error": f"GM回答文件不存在：{gm_path}"}
    gm_text = gm_path.read_text(encoding="utf-8")

    violations = [term for term in FORBIDDEN_TERMS if term in gm_text]

    pending = engine.state.meta.get("pending_options", {})
    if isinstance(pending, dict) and pending.get("options"):
        for key, option in pending["options"].items():
            if isinstance(option, dict) and option.get("label"):
                if str(option["label"]) not in gm_text and key not in gm_text:
                    violations.append(f"选项{key}标签未在叙述中展示")

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
    parser = argparse.ArgumentParser(description="统一回合入口（两阶段）")
    parser.add_argument("save_dir", type=str)
    parser.add_argument("phase", choices=["resolve", "record"], help="阶段：resolve=结算, record=记录叙述")
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
    else:
        result = record_phase(engine, save_dir, args)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
