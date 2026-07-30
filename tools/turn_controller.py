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

from engine_runtime.events import TIME_PERIOD_STARTS
from engine_runtime.narrative_log import record_narrative_turn
from engine_runtime.presentation import player_facing_result
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


# ─── 智能候选生成 ───────────────────────────────────────────────────


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
                        {"action_id": "wait-step", "type": "WAIT", "parameters": {"wait_minutes": int(best_wait)}, "goal": f"等待进入{locked['allowed_periods'][0]}"},
                        {"action_id": "action-step", "type": locked["action_type"], "target": locked["target_id"], "goal": locked["label"]},
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


# ─── 核心：resolve 阶段 ─────────────────────────────────────────────


def resolve(engine: GameEngine, player_input: str, action_json: str | None = None, generate_options_only: bool = False) -> dict:
    """统一结算入口。

    路由逻辑：
    1. 检测 player_input 是否匹配 pending_options 中的选项 → 直接执行合同
    2. 如果提供了 action_json → 执行自由行动
    3. generate_options_only → 仅刷新选项
    """
    execution_result = None
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

    # 生成下一回合候选并编译
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
    }
    if errors:
        package["errors"] = errors
    if execution_result:
        package["resolved"] = player_facing_result(execution_result)

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

    assert_startable(save_dir)
    state = load_game_state(save_dir)
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
