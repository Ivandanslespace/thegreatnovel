#!/usr/bin/env python3
"""
TheGreatNovel 存档校验器
实现 engine/validators.md 中定义的十一类校验。

用法：
    python validate_save.py <存档路径>
    python validate_save.py saves/渊驮

输出：按严重度分组的校验结果（CRITICAL / ERROR / WARNING / INFO）

校验类别:
1. 连续性校验 - 存档完整性与事件源一致性
2. 规则校验 - 事件队列、灾难周期等游戏机制
3. 知识校验 - 情报降级与认知安全
4. 战力校验 - 战斗平衡与等级关系
5. 关系校验 - NPC 态度与信任值协调
6. 叙事校验 - 悬念、伏笔与叙述长度
7. 人口一致性 - NPC、种族、派系逻辑自洽
8. 对比一致性 - 跨存档进度比例合理性
9. 公共系统一致性 - 经济、基建、公共服务逻辑
10. 流派一致性 - 废土列车主题设定符合度
11. 选项质量 - 待处理选项的可用性与多样性
"""

import sys
import os
import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    import yaml
except ImportError:
    print("需要 PyYAML: pip install pyyaml")
    sys.exit(1)

from engine_runtime.ratings import RATING_INDEX
from engine_runtime.world_compiler import COMPILER_VERSION


# ─── 工具函数 ───────────────────────────────────────────────

def load_yaml(path):
    """加载 YAML 文件，返回 dict 或 None。"""
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_text(path):
    """加载文本文件。"""
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


LEGACY_EVENT_FORMAT_THROUGH_TURN = 16
REQUIRED_SAVE_FILES = (
    "world.yaml",
    "player.yaml",
    "base.yaml",
    "inventory.yaml",
    "npcs.yaml",
    "factions.yaml",
    "relationships.yaml",
    "event_queue.yaml",
    "event_log.md",
    "story.md",
    "meta.yaml",
)
VALID_DIFFICULTIES = {"休闲", "标准", "硬核"}
VALID_DEATH_MODES = {"permanent", "checkpoint", "legacy"}


def parse_event_blocks(event_log):
    """解析 event_log.md 中的 Turn 事件，兼容迁移期旧格式。"""
    events = []
    errors = []
    pattern = re.compile(
        r"^## Turn\s+(\d+)\s+\|[^\n]*\n(.*?)(?=^---\s*$|^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )

    for match in pattern.finditer(event_log):
        turn = int(match.group(1))
        block = match.group(0)
        json_match = re.search(r"```json\s*(.*?)```", block, re.DOTALL)
        if not json_match:
            errors.append(f"Turn {turn} 缺少 JSON 事件体")
            continue

        try:
            payload = json.loads(json_match.group(1))
        except json.JSONDecodeError as exc:
            errors.append(f"Turn {turn} JSON 无法解析：{exc.msg}")
            continue

        records = payload if isinstance(payload, list) else [payload]
        for record in records:
            if not isinstance(record, dict):
                errors.append(f"Turn {turn} 事件不是对象")
                continue
            events.append({
                "turn": turn,
                "data": record,
                "text": block,
            })

    events.sort(key=lambda event: event["turn"])
    return events, errors


def event_text(event):
    """返回事件的可搜索文本，不包含快照和文件头部注释。"""
    return event["text"] + "\n" + json.dumps(
        event["data"], ensure_ascii=False, sort_keys=True
    )


def event_location(event):
    data = event["data"]
    location = data.get("location")
    if location:
        return str(location)
    nested = data.get("data")
    if isinstance(nested, dict) and nested.get("location"):
        return str(nested["location"])
    return ""


def relationship_map(raw_relationships):
    """兼容当前列表格式和旧的按 npc_id 索引格式。"""
    if isinstance(raw_relationships, dict):
        return raw_relationships
    if isinstance(raw_relationships, list):
        return {
            item.get("npc_id"): item
            for item in raw_relationships
            if isinstance(item, dict) and item.get("npc_id")
        }
    return {}


def extract_day(value):
    if value is None:
        return None
    match = re.search(r"(?:第\s*)?(\d+)\s*天|Day\s*(\d+)|game_day_equals_(\d+)", str(value), re.I)
    if not match:
        return None
    return int(next(group for group in match.groups() if group is not None))


def requires_standard_event(data, event):
    """新生成存档从首回合起使用标准事件；旧存档保留历史迁移窗口。"""
    format_version = data.get("meta", {}).get("event_format_version", 1)
    return format_version >= 2 or event["turn"] > LEGACY_EVENT_FORMAT_THROUGH_TURN


class Finding:
    def __init__(self, severity, category, message):
        self.severity = severity  # CRITICAL / ERROR / WARNING / INFO
        self.category = category  # 六类之一
        self.message = message

    def __repr__(self):
        return f"[{self.severity}] ({self.category}) {self.message}"


def validate_world_package(save_dir, data):
    """校验新游戏生成契约，避免只校验到一份残缺存档。"""
    findings = []
    missing_files = [name for name in REQUIRED_SAVE_FILES if not (save_dir / name).exists()]
    if missing_files:
        findings.append(Finding(
            "CRITICAL", "连续性",
            f"存档缺少必需文件：{', '.join(missing_files)}"
        ))

    world = data.get("world", {})
    meta = data.get("meta", {})
    setting = world.get("setting", {}) if isinstance(world, dict) else {}
    resources = world.get("resources", {}) if isinstance(world, dict) else {}
    rules = world.get("rules", {}) if isinstance(world, dict) else {}
    death = rules.get("death", {}) if isinstance(rules, dict) else {}
    disaster = rules.get("disaster", {}) if isinstance(rules, dict) else {}
    talent = data.get("player_talent", {})

    required_values = {
        "world.name": world.get("name"),
        "world.theme": world.get("theme"),
        "world.setting.safe_base": setting.get("safe_base"),
        "world.setting.exploration_method": setting.get("exploration_method"),
        "meta.world_name": meta.get("world_name"),
        "meta.current_location": meta.get("current_location"),
        "meta.language": meta.get("language"),
    }
    for field, value in required_values.items():
        if value in (None, ""):
            findings.append(Finding("CRITICAL", "规则", f"必填字段为空：{field}"))

    if not isinstance(setting.get("external_dangers"), list) or not setting["external_dangers"]:
        findings.append(Finding("CRITICAL", "规则", "world.setting.external_dangers 至少需要一项"))
    primary = resources.get("primary")
    if not isinstance(primary, list) or not 3 <= len(primary) <= 5:
        findings.append(Finding("CRITICAL", "规则", "world.resources.primary 必须包含3到5种资源"))

    if world.get("difficulty") not in VALID_DIFFICULTIES:
        findings.append(Finding("ERROR", "规则", "world.difficulty 必须是休闲、标准或硬核"))
    narrative_length = meta.get("narrative_length", world.get("narrative_length"))
    if not isinstance(narrative_length, int) or not 1 <= narrative_length <= 10:
        findings.append(Finding("ERROR", "叙事", "narrative_length 必须是1到10的整数"))
    if death.get("type") not in VALID_DEATH_MODES:
        findings.append(Finding("ERROR", "规则", "world.rules.death.type 必须是 permanent/checkpoint/legacy"))

    cycle_days = disaster.get("cycle_days")
    if not isinstance(cycle_days, int) or cycle_days < 1:
        findings.append(Finding("ERROR", "规则", "world.rules.disaster.cycle_days 必须是正整数"))
    if not disaster.get("first_event"):
        findings.append(Finding("ERROR", "规则", "world.rules.disaster.first_event 不能为空"))

    talent_fields = ("name", "description", "type", "trigger", "effect", "limitations", "rarity")
    if not isinstance(talent, dict):
        findings.append(Finding("CRITICAL", "规则", "world.yaml 缺少 player_talent 对象"))
    else:
        missing_talent = [field for field in talent_fields if not talent.get(field)]
        if missing_talent:
            findings.append(Finding(
                "CRITICAL", "规则",
                f"player_talent 缺少字段：{', '.join(missing_talent)}"
            ))
        elif talent.get("rarity") not in RATING_INDEX:
            findings.append(Finding("ERROR", "规则", "player_talent.rarity 必须是 G/F/E/D/C/B/A/S/SS/SSS"))

    player = data.get("player", {}) if isinstance(data.get("player", {}), dict) else {}
    talent_list = player.get("talents", []) if isinstance(player.get("talents", []), list) else []
    for index, item in enumerate(talent_list):
        if isinstance(item, dict) and item.get("rarity") not in RATING_INDEX:
            findings.append(Finding("ERROR", "规则", f"player.talents[{index}].rarity 必须是 G/F/E/D/C/B/A/S/SS/SSS"))
    inventory = data.get("inventory", {}) if isinstance(data.get("inventory", {}), dict) else {}
    equipment = inventory.get("equipment", {}) if isinstance(inventory.get("equipment", {}), dict) else {}
    for slot, item in equipment.items():
        if isinstance(item, dict) and item.get("rarity") not in RATING_INDEX:
            findings.append(Finding("ERROR", "规则", f"inventory.equipment.{slot}.rarity 必须是 G/F/E/D/C/B/A/S/SS/SSS"))
    items = inventory.get("items", []) if isinstance(inventory.get("items", []), list) else []
    for index, item in enumerate(items):
        if isinstance(item, dict) and item.get("rarity") not in RATING_INDEX:
            findings.append(Finding("ERROR", "规则", f"inventory.items[{index}].rarity 必须是 G/F/E/D/C/B/A/S/SS/SSS"))

    generation = world.get("generation", {}) if isinstance(world.get("generation", {}), dict) else {}
    registered_locations = world.get("locations", [])
    if isinstance(registered_locations, list):
        registered_location_ids = {str(item.get("id", item.get("name"))) for item in registered_locations if isinstance(item, dict) and item.get("id", item.get("name"))}
    elif isinstance(registered_locations, dict):
        registered_location_ids = {str(key) for key in registered_locations}
    else:
        registered_location_ids = set()
    current_location = meta.get("current_location")
    if current_location and registered_location_ids and str(current_location) not in registered_location_ids:
        findings.append(Finding("CRITICAL", "连续性", f"meta.current_location 未注册：{current_location}"))
    if generation.get("mechanics_source") in {"theme_profile", "llm_world_blueprint", "llm_compiled_bundle"}:
        bundle = world.get("generation_bundle")
        required_bundle = ("starting_location", "locations", "enemies", "areas", "build_catalog", "action_targets", "starting_inventory")
        if not isinstance(bundle, dict):
            findings.append(Finding("CRITICAL", "规则", "创作世界缺少 generation_bundle"))
        else:
            missing_bundle = [field for field in required_bundle if not bundle.get(field)]
            if missing_bundle:
                findings.append(Finding("CRITICAL", "规则", f"generation_bundle 缺少可执行字段：{', '.join(missing_bundle)}"))
            if generation.get("mechanics_source") != "theme_profile" and str(bundle.get("compiler_version", "")) != str(COMPILER_VERSION):
                findings.append(Finding("CRITICAL", "规则", f"generation_bundle.compiler_version={bundle.get('compiler_version')} 与当前编译器 {COMPILER_VERSION} 不兼容"))
            location_values = bundle.get("locations", [])
            location_ids = {
                str(item.get("id", item.get("name"))) for item in location_values
                if isinstance(item, dict) and item.get("id", item.get("name"))
            } if isinstance(location_values, list) else {str(key) for key in location_values} if isinstance(location_values, dict) else set()
            if current_location and not registered_location_ids and str(current_location) not in location_ids:
                findings.append(Finding("CRITICAL", "连续性", f"meta.current_location 未注册：{current_location}"))
        if generation.get("mechanics_source") == "llm_world_blueprint" and not isinstance(world.get("world_blueprint"), dict):
            findings.append(Finding("CRITICAL", "规则", "LLM 原创世界缺少 world_blueprint"))
        if not (save_dir / "campaign.sqlite3").exists():
            findings.append(Finding("CRITICAL", "连续性", "创作世界缺少 SQLite 事件存储 campaign.sqlite3"))
        else:
            try:
                from engine_runtime.events import apply_event
                from engine_runtime.persistence import SQLiteEventStore

                store = SQLiteEventStore(save_dir / "campaign.sqlite3")
                projection = store.verify_projection(apply_event)
                if not projection.get("ok"):
                    findings.append(Finding("CRITICAL", "连续性", "SQLite 事件重放结果与最新投影不一致"))
                snapshot = store.latest_snapshot() or {}
                view_keys = (
                    "world", "player", "base", "inventory", "npcs", "factions", "relationships", "event_queue",
                    "region_state", "population_state", "public_system_state", "market_state", "ranking_state",
                    "comparative_state", "rival_state", "meta", "player_talent",
                )
                yaml_view = {key: data.get(key, {}) for key in view_keys}
                sql_view = {key: snapshot.get(key, {}) for key in view_keys}
                if yaml_view != sql_view:
                    mismatches = [key for key in view_keys if yaml_view.get(key) != sql_view.get(key)]
                    findings.append(Finding("CRITICAL", "连续性", "YAML 导出视图与 SQLite 最新快照不一致：" + ", ".join(mismatches)))
            except (OSError, ValueError, RuntimeError) as exc:
                findings.append(Finding("CRITICAL", "连续性", f"SQLite 投影校验失败：{exc}"))

    current_turn = meta.get("current_turn")
    if not isinstance(current_turn, int) or current_turn < 1:
        findings.append(Finding("ERROR", "连续性", "meta.current_turn 必须是正整数"))
    if meta.get("world_name") and world.get("name") and meta["world_name"] != world["name"]:
        findings.append(Finding("ERROR", "连续性", "meta.world_name 与 world.name 不一致"))
    pending_options = meta.get("pending_options")
    if pending_options:
        if not isinstance(pending_options, dict) or not isinstance(pending_options.get("options"), dict):
            findings.append(Finding("CRITICAL", "连续性", "pending_options 必须包含 options 映射"))
        else:
            for option_id, option in pending_options["options"].items():
                if not isinstance(option, dict) or not isinstance(option.get("action"), dict):
                    findings.append(Finding("CRITICAL", "连续性", f"pending_options.{option_id} 缺少已绑定 action 契约"))
                preview = option.get("preview") if isinstance(option, dict) else None
                if not isinstance(preview, dict) or preview.get("legal") is not True:
                    findings.append(Finding("CRITICAL", "连续性", f"pending_options.{option_id} 没有合法的预验证结果"))
            if pending_options.get("state_turn") != current_turn:
                findings.append(Finding("CRITICAL", "连续性", "pending_options 与当前回合不一致"))
    if meta.get("event_format_version", 1) >= 2 and not data.get("events"):
        findings.append(Finding("CRITICAL", "连续性", "标准事件存档至少需要一条初始事件"))
    return findings


# ─── 校验器 ─────────────────────────────────────────────────

def validate_continuity(save_dir, data):
    """一、连续性校验"""
    findings = []
    meta = data.get("meta", {})
    player = data.get("player", {})
    inventory = data.get("inventory", {})
    npcs = data.get("npcs", [])
    events = data.get("events", [])

    # 检查已死NPC是否在最近事件中出现
    dead_npcs = [n for n in npcs if n.get("status") == "dead"]
    for npc in dead_npcs:
        name = npc.get("name", npc.get("id", "unknown"))
        # 检查最近5个Turn的事件中是否提到该NPC
        recent_events = events[-5:]
        for event in recent_events:
            text = event_text(event)
            if name in text and "回忆" not in text and "纪念" not in text:
                findings.append(Finding(
                    "CRITICAL", "连续性",
                    f"已死NPC「{name}」在近期事件中被提及（可能违规出场）"
                ))

    # 检查NPC是否有日程字段
    for npc in npcs:
        name = npc.get("name", npc.get("id", "unknown"))
        if "schedule" not in npc:
            findings.append(Finding(
                "WARNING", "连续性",
                f"NPC「{name}」缺少 schedule 字段（行动经济系统需要）"
            ))

    # 检查 meta.current_location 是否与最近事件一致
    current_loc = meta.get("current_location", "")
    if current_loc and events:
        last_event_loc = event_location(events[-1])
        if last_event_loc and current_loc not in last_event_loc and last_event_loc not in current_loc:
            findings.append(Finding(
                "WARNING", "连续性",
                f"meta.current_location「{current_loc}」与最后事件地点「{last_event_loc}」不完全匹配"
            ))

    return findings


def validate_rules(save_dir, data):
    """二、规则校验"""
    findings = []
    meta = data.get("meta", {})
    world = data.get("world", {})
    event_queue = data.get("event_queue", [])
    events = data.get("events", [])
    current_turn = meta.get("current_turn", 0)
    game_day = meta.get("game_day", 1)

    event_ids = [evt.get("id") for evt in event_queue if isinstance(evt, dict)]
    duplicate_ids = sorted({evt_id for evt_id in event_ids if event_ids.count(evt_id) > 1})
    if duplicate_ids:
        findings.append(Finding(
            "ERROR", "规则",
            f"event_queue 存在重复事件ID：{', '.join(duplicate_ids)}"
        ))

    # 检查事件队列：pending事件是否已超过latest_turn
    for evt in event_queue:
        if not isinstance(evt, dict):
            continue
        evt_id = evt.get("id", "unknown")
        status = evt.get("status", "pending")
        latest = evt.get("latest_turn", 999)

        if status == "pending" and current_turn > latest:
            findings.append(Finding(
                "ERROR", "规则",
                f"事件「{evt_id}」已超过最晚触发回合（latest={latest}, current={current_turn}），"
                f"应标记为 expired 或 triggered"
            ))

        triggered_turn = evt.get("triggered_turn")
        earliest = evt.get("earliest_turn", 0)
        if status == "triggered":
            if not isinstance(triggered_turn, int):
                findings.append(Finding(
                    "ERROR", "规则",
                    f"事件「{evt_id}」状态为 triggered，但 triggered_turn 无效"
                ))
            elif triggered_turn > current_turn or triggered_turn < earliest:
                findings.append(Finding(
                    "ERROR", "规则",
                    f"事件「{evt_id}」的 triggered_turn={triggered_turn} 不在有效范围"
                ))

    # 检查灾难周期一致性
    rules = world.get("rules", {}) if world else {}
    disaster = rules.get("disaster", {})
    cycle_days = disaster.get("cycle_days", 0)
    first_event = disaster.get("first_event", "")

    if cycle_days and first_event:
        # 提取first_event中的天数
        day_match = re.search(r"(\d+)", str(first_event))
        if day_match:
            first_day = int(day_match.group(1))
            if game_day > first_day + cycle_days:
                # 应该有第二次蜕震了
                findings.append(Finding(
                    "WARNING", "规则",
                    f"当前Day{game_day}，第一次蜕震Day{first_day}，周期{cycle_days}天——"
                    f"第二次蜕震应在Day{first_day + cycle_days}，请确认是否已安排"
                ))

            disaster_events = []
            for event in events:
                data_text = event_text(event)
                event_type = str(event["data"].get("event_type", event["data"].get("type", "")))
                if "disaster" in event_type.lower() or "蜕震开始" in data_text or "DISASTER_OCCURRED" in data_text:
                    disaster_events.append(event)
            if disaster_events:
                observed_day = disaster_events[0]["data"].get("day")
                if observed_day is None:
                    observed_day = extract_day(event_text(disaster_events[0]))
                if observed_day is not None and observed_day != first_day:
                    findings.append(Finding(
                        "ERROR", "规则",
                        f"world.yaml first_event=Day{first_day}，但事件日志记录首次灾难为Day{observed_day}"
                    ))

            first_queue_event = next(
                (evt for evt in event_queue if isinstance(evt, dict) and evt.get("id") == "event_001"),
                None,
            )
            if first_queue_event:
                queue_day = extract_day(first_queue_event.get("trigger_conditions"))
                if queue_day is not None and queue_day != first_day:
                    findings.append(Finding(
                        "ERROR", "规则",
                        f"world.yaml first_event=Day{first_day}，但 event_001 触发条件为Day{queue_day}"
                    ))

    # 检查 meta 中是否有 narrative_length 和 language
    if "narrative_length" not in meta:
        findings.append(Finding(
            "WARNING", "规则",
            "meta.yaml 缺少 narrative_length 字段"
        ))
    if "language" not in meta:
        findings.append(Finding(
            "WARNING", "规则",
            "meta.yaml 缺少 language 字段"
        ))

    return findings


def validate_knowledge(save_dir, data):
    """三、知识校验"""
    findings = []
    story_text = data.get("story_text", "")
    event_log = data.get("event_log_text", "")

    for source_name, source_text in (("story.md", story_text), ("event_log.md", event_log)):
        for line in source_text.splitlines():
            has_confirmed_claim = any([
                "战略认知：" in line,
                "战略认知:" in line,
                "真正解法=" in line,
                "真正解法＝" in line,
                "真正解法:" in line,
                "堡垒思路不可行" in line,
            ])
            has_uncertainty_marker = any([
                "初步假设" in line,
                "未确认" in line,
                "待验证" in line,
                "可能无法" in line,
                "可能不能" in line,
            ])
            if has_confirmed_claim and not has_uncertainty_marker:
                findings.append(Finding(
                    "ERROR", "知识",
                    f"{source_name} 中存在未经降级的高级情报表述：{line.strip()}"
                ))

    # 检查是否有"确认"语气的高级情报（应该是假设）
    confirmed_patterns = [
        r"战略认知[：:]",
        r"真正解法[＝=]",
        r"答案(?:就)?在",
        r"不可行[。，]",
    ]
    for pattern in confirmed_patterns:
        matches = re.findall(pattern, story_text)
        if matches:
            findings.append(Finding(
                "ERROR", "知识",
                f"story.md 中发现确认语气的高级情报（匹配: {matches[0]}）——"
                f"应降级为「未确认假设」"
            ))

    # 检查 event_log 中是否有 strategic_insight 字段（应改为 hypothesis_formed）
    if "strategic_insight" in event_log:
        findings.append(Finding(
            "ERROR", "知识",
            "event_log.md 中存在 'strategic_insight' 字段——"
            "应使用 'hypothesis_formed' 并标注（未确认）"
        ))

    return findings


def validate_combat(save_dir, data):
    """四、战力校验"""
    findings = []
    player = data.get("player", {})
    npcs = data.get("npcs", [])
    event_log = data.get("event_log_text", "")

    player_level = player.get("level", 1) if player else 1

    # 检查是否有越级战斗记录（简单启发式）
    combat_events = re.findall(r'"event_type":\s*"combat[^"]*"', event_log)
    if combat_events:
        # 如果有战斗事件，检查是否有等级差过大的情况
        for npc in npcs:
            npc_level = npc.get("level", 1)
            if npc.get("status") == "dead" and npc_level - player_level > 3:
                findings.append(Finding(
                    "WARNING", "战力",
                    f"NPC「{npc.get('name')}」(Lv{npc_level})已死亡，"
                    f"与主角(Lv{player_level})等级差>{3}，请确认战斗合理性"
                ))

    return findings


def validate_relationships(save_dir, data):
    """五、关系校验"""
    findings = []
    npcs = data.get("npcs", [])
    relationships = relationship_map(data.get("relationships", {}))

    # 检查NPC态度标签是否与关系数值一致
    for npc in npcs:
        name = npc.get("name", npc.get("id", "unknown"))
        attitude = npc.get("attitude_to_player", "neutral")

        # 如果attitude是friendly/loyal但relationships中trust很低
        rel = relationships.get(npc.get("id"), {})
        if not rel:
            findings.append(Finding(
                "WARNING", "关系",
                f"NPC「{name}」缺少对应关系记录"
            ))
            continue
        trust = rel.get("trust", 50) if isinstance(rel, dict) else 50
        if attitude in ("friendly", "loyal") and trust < 20:
            findings.append(Finding(
                "ERROR", "关系",
                f"NPC「{name}」attitude={attitude} 但 trust={trust}，数值与标签矛盾"
            ))
        if attitude == "hostile" and trust > 60:
            findings.append(Finding(
                "ERROR", "关系",
                f"NPC「{name}」attitude=hostile 但 trust={trust}，数值与标签矛盾"
            ))

    return findings


def validate_narrative(save_dir, data):
    """六、叙事校验"""
    findings = []
    meta = data.get("meta", {})
    event_log = data.get("event_log_text", "")
    events = data.get("events", [])
    current_turn = meta.get("current_turn", 0)

    # 检查活跃悬念数量（上限5）
    mysteries = meta.get("active_mysteries", [])
    if len(mysteries) > 5:
        findings.append(Finding(
            "ERROR", "叙事",
            f"活跃悬念数量为 {len(mysteries)}，超过上限5条——"
            f"请合并或归档次要悬念"
        ))

    # 检查快照是否存在（每10轮应有快照）
    expected_snapshots = current_turn // 10
    actual_snapshots = len(re.findall(r"SNAPSHOT\s*\|\s*Turn\s+\d+", event_log))
    campaign_path = save_dir / "campaign.sqlite3"
    if campaign_path.exists():
        try:
            with sqlite3.connect(campaign_path) as connection:
                actual_snapshots = connection.execute(
                    "SELECT COUNT(*) FROM snapshots WHERE campaign_id=? AND turn > 0 AND turn % 10 = 0",
                    (campaign_path.parent.name,),
                ).fetchone()[0]
        except sqlite3.Error:
            # SQLite 连续性问题由专门的事件源校验报告；这里保留 Markdown 兼容回退。
            pass
    if actual_snapshots < expected_snapshots:
        findings.append(Finding(
            "WARNING", "叙事",
            f"当前Turn {current_turn}，应有 {expected_snapshots} 个快照，"
            f"实际找到 {actual_snapshots} 个"
        ))

    # 检查叙述长度设置
    narrative_length = meta.get("narrative_length", 7)
    if narrative_length < 1 or narrative_length > 10:
        findings.append(Finding(
            "ERROR", "叙事",
            f"narrative_length={narrative_length} 超出有效范围(1-10)"
        ))

    # 检查 foreshadowing 数量（不宜过多）
    foreshadowing = meta.get("foreshadowing_active", [])
    if len(foreshadowing) > 8:
        findings.append(Finding(
            "WARNING", "叙事",
            f"活跃伏笔数量为 {len(foreshadowing)}，过多可能导致叙事负担"
        ))

    # Turn 17 起，每个标准事件必须有 event_id；旧事件允许迁移期格式。
    new_events = [event for event in events if requires_standard_event(data, event)]
    missing_ids = [str(event["turn"]) for event in new_events if not event["data"].get("event_id")]
    if missing_ids:
        findings.append(Finding(
            "ERROR", "叙事",
            f"Turn 17 起的事件缺少 event_id：{', '.join(missing_ids)}"
        ))

    event_ids = [event["data"].get("event_id") for event in new_events if event["data"].get("event_id")]
    duplicate_event_ids = sorted({event_id for event_id in event_ids if event_ids.count(event_id) > 1})
    if duplicate_event_ids:
        findings.append(Finding(
            "ERROR", "叙事",
            f"事件日志存在重复 event_id：{', '.join(duplicate_event_ids)}"
        ))

    return findings


def validate_event_sourcing(save_dir, data):
    """检查事件 JSON 是否可解析，并确保标准事件没有被快照或注释遮蔽。"""
    findings = []
    for error in data.get("event_parse_errors", []):
        findings.append(Finding("CRITICAL", "连续性", error))

    for event in data.get("events", []):
        if not requires_standard_event(data, event):
            continue
        record = event["data"]
        required_fields = ("event_id", "type", "actor", "turn", "timestamp")
        missing = [field for field in required_fields if field not in record]
        if missing:
            findings.append(Finding(
                "ERROR", "连续性",
                f"Turn {event['turn']} 标准事件缺少字段：{', '.join(missing)}"
            ))
    return findings


def validate_action_economy(save_dir, data):
    """Turn 17 起检查涉及玩家的事件是否记录行动成本。"""
    findings = []
    for event in data.get("events", []):
        if not requires_standard_event(data, event):
            continue

        record = event["data"]
        actors = record.get("actors", [])
        actor = record.get("actor")
        payload = record.get("data", {}) if isinstance(record.get("data"), dict) else {}
        involves_player = actor == "player" or "player" in actors or payload.get("actor") == "player"
        if not involves_player:
            continue

        ledger = payload.get("action_ledger") or record.get("action_ledger")
        if not isinstance(ledger, dict):
            findings.append(Finding(
                "ERROR", "规则",
                f"Turn {event['turn']} 涉及玩家，但缺少 action_ledger"
            ))
            continue

        for field in ("available_time_minutes", "available_stamina", "available_mental", "actions"):
            if field not in ledger:
                findings.append(Finding(
                    "ERROR", "规则",
                    f"Turn {event['turn']} action_ledger 缺少字段：{field}"
                ))

        actions = ledger.get("actions", [])
        if not isinstance(actions, list):
            findings.append(Finding(
                "ERROR", "规则",
                f"Turn {event['turn']} action_ledger.actions 必须是列表"
            ))
            continue

        required_action_fields = ("type", "time_minutes", "stamina_cost", "mental_cost", "tags")
        for index, action in enumerate(actions, start=1):
            if not isinstance(action, dict):
                findings.append(Finding(
                    "ERROR", "规则",
                    f"Turn {event['turn']} action_{index} 不是对象"
                ))
                continue
            missing = [field for field in required_action_fields if field not in action]
            if missing:
                findings.append(Finding(
                    "ERROR", "规则",
                    f"Turn {event['turn']} action_{index} 缺少字段：{', '.join(missing)}"
                ))
    return findings


def validate_formula_trace(save_dir, data):
    """标准引擎事件必须携带可复盘的公式结果，而不是只有叙述。"""
    findings = []
    engine_event_types = {"ACTION_RESOLVED", "EXPLORATION_RESOLVED", "RESEARCH_RESOLVED", "SOCIAL_RESOLVED", "COMBAT_RESOLVED", "BATCH_ACTION_RESOLVED", "BUILDING_BUILT", "BASE_MAINTENANCE", "ATTRIBUTES_ALLOCATED"}
    for event in data.get("events", []):
        if not requires_standard_event(data, event):
            continue
        record = event["data"]
        if record.get("type") not in engine_event_types:
            continue
        payload = record.get("data", {}) if isinstance(record.get("data"), dict) else {}
        resolution = payload.get("resolution")
        if not isinstance(resolution, dict):
            findings.append(Finding(
                "ERROR", "战力",
                f"Turn {event['turn']} 引擎事件缺少 data.resolution 公式结果"
            ))
            continue
        required = ("formula_version",)
        if record.get("type") in {"ACTION_RESOLVED", "COMBAT_RESOLVED", "BATCH_ACTION_RESOLVED"}:
            required = (*required, "outcome")
        missing = [field for field in required if field not in resolution]
        if missing:
            findings.append(Finding(
                "ERROR", "战力",
                f"Turn {event['turn']} 公式结果缺少字段：{', '.join(missing)}"
            ))
        for field in ("probability", "severity"):
            if field in resolution:
                try:
                    float(resolution[field])
                except (TypeError, ValueError):
                    findings.append(Finding(
                        "ERROR", "战力",
                        f"Turn {event['turn']} 公式字段 {field} 不是数值"
                    ))
    return findings


def validate_population_consistency(save_dir, data):
    """七、人口一致性校验 - 确保 NPC、种族、势力之间的人口逻辑自洽。"""
    findings = []
    
    npcs = data.get("npcs", [])
    factions = data.get("factions", [])
    relationships = relationship_map(data.get("relationships", {}))
    world = data.get("world", {})
    setting = world.get("setting", {}) if isinstance(world, dict) else {}
    
    # 1. 检查 NPC 是否在相关 faction 中注册
    for npc in npcs:
        npc_id = npc.get("id", "unknown")
        npc_name = npc.get("name", "未知角色")
        npc_faction = npc.get("faction")
        
        if npc_faction:
            found_in_factions = False
            for faction in factions:
                if faction.get("id") == npc_faction or faction.get("name") == npc_faction:
                    found_in_factions = True
                    break
            
            if not found_in_factions:
                findings.append(Finding(
                    "WARNING", "人口一致性",
                    f"NPC「{npc_name}」(ID:{npc_id}) 所属派系'{npc_faction}'未在世界中注册"
                ))
    
    # 2. 检查派系成员数与 NPC 数量是否合理匹配
    for faction in factions:
        faction_id = faction.get("id", "unknown")
        faction_name = faction.get("name", "未知派系")
        expected_members = faction.get("member_count", 0)
        actual_members = sum(1 for npc in npcs if npc.get("faction") == faction_id)
        
        # 允许一定的误差范围 (±20% 或绝对值差异不超过 3)
        tolerance = max(int(expected_members * 0.2), 3)
        difference = abs(actual_members - expected_members)
        
        if difference > tolerance:
            findings.append(Finding(
                "WARNING", "人口一致性",
                f"派系'{faction_name}'实际成员数({actual_members})与声明的成员数({expected_members})差异过大 (差异：{difference})"
            ))
    
    # 3. 检查 NPC 状态与人口统计
    alive_npcs = [n for n in npcs if n.get("status") != "dead"]
    dead_npcs = [n for n in npcs if n.get("status") == "dead"]
    
    # 检查死亡 NPC 是否有 death_turn
    for npc in dead_npcs:
        if "death_turn" not in npc:
            name = npc.get("name", npc.get("id", "unknown"))
            findings.append(Finding(
                "ERROR", "人口一致性",
                f"已死 NPC「{name}」缺少死亡回合 (death_turn)"
            ))
    
    # 4. 检查年龄合理性（NPC 年龄不应超过世界最大寿命）
    max_lifespan = setting.get("max_lifespan", 150)
    for npc in npcs:
        age = npc.get("age")
        if age and isinstance(age, (int, float)):
            if age > max_lifespan * 1.5:  # 允许 50% 缓冲 (可能是不死生物等特殊设定)
                findings.append(Finding(
                    "WARNING", "人口一致性",
                    f"NPC「{npc.get('name')}」年龄 ({age}) 超过合理范围 (上限~{max_lifespan})"
                ))
    
    # 5. 检查种族与属性的协调性
    valid_races = setting.get("valid_races", ["人类", "变异体", "机械体"])
    for npc in npcs:
        race = npc.get("race")
        if race and race not in valid_races:
            name = npc.get("name", npc.get("id", "unknown"))
            findings.append(Finding(
                "WARNING", "人口一致性",
                f"NPC「{name}」的种族 '{race}' 未在世界配置中定义"
            ))
    
    # 6. 检查关系网络完整性
    orphan_npcs = [npc for npc in npcs if not relationships.get(npc.get("id", ""))]
    if len(orphan_npcs) > len(npcs) * 0.7:  # 超过 70% 的 NPC 没有关系记录
        findings.append(Finding(
            "WARNING", "人口一致性",
            f"人口网络稀疏：{len(orphan_npcs)}/{len(npcs)} 的 NPC 没有建立关系网络"
        ))
    
    return findings


def validate_comparative_consistency(save_dir, data):
    """八、对比一致性校验 - 确保跨存档/版本的数据保持一致性。"""
    findings = []
    
    meta = data.get("meta", {})
    player = data.get("player", {})
    world = data.get("world", {})
    events = data.get("events", [])
    
    current_turn = meta.get("current_turn", 0)
    
    # 1. 检查存档生成代数是否与 meta 一致
    generation = world.get("generation", {})
    recorded_generation = meta.get("generation", {}).get("world_generation", 0)
    generated_fields = generation.get("generated_fields", {})
    
    if recorded_generation != generation.get("world_generation", 0):
        findings.append(Finding(
            "ERROR", "对比一致性",
            f"存档代数不一致：meta.yaml 记录为{recorded_generation}, world.yaml 声明为{generation.get('world_generation')}"
        ))
    
    # 2. 检查游戏进度与玩家等级的比例合理性
    player_level = player.get("level", 1)
    
    # Turn 1-5: Level 1-3
    # Turn 6-15: Level 3-8
    # Turn 16+: Level 8+
    
    expected_level_range = None
    if current_turn <= 5:
        expected_level_range = (1, 3)
    elif current_turn <= 15:
        expected_level_range = (3, 8)
    else:
        expected_level_range = (8, min(current_turn // 2 + 5, 50))
    
    if expected_level_range:
        if player_level < expected_level_range[0]:
            findings.append(Finding(
                "INFO", "对比一致性",
                f"玩家等级 ({player_level}) 低于预期范围 [{expected_level_range[0]}, ...]，可能存在跳过成长经历"
            ))
        elif player_level > expected_level_range[1]:
            findings.append(Finding(
                "WARNING", "对比一致性",
                f"玩家等级 ({player_level}) 高于当前回合 ({current_turn}) 的预期范围 [..., {expected_level_range[1]}]"
            ))
    
    # 3. 检查经验值与等级的匹配
    exp = player.get("experience", 0)
    level = player.get("level", 1)
    
    # 简单经验曲线检查：每级需要 ~level*100 经验
    expected_exp = sum((i + 1) * 100 for i in range(level))
    if exp < expected_exp * 0.5:
        findings.append(Finding(
            "WARNING", "对比一致性",
            f"玩家经验 ({exp}) 明显低于等级 ({level}) 的预期值 (~{expected_exp})"
        ))
    
    # 4. 检查资源数量与回合数的比例
    inventory = data.get("inventory", {})
    resources = inventory.get("items", [])
    
    # 计算总资源数
    total_resources = len(resources)
    
    # 平均每回合获取资源量应在合理范围内 (1-10 个/回合)
    if current_turn > 0:
        avg_resources_per_turn = total_resources / current_turn
        if avg_resources_per_turn > 20:
            findings.append(Finding(
                "WARNING", "对比一致性",
                f"资源获取速度异常：平均每回合{avg_resources_per_turn:.1f}个 (建议<10 个/回合)"
            ))
    
    # 5. 检查地点变更频率
    if events and len(events) > 1:
        locations_changed = set()
        for event in events:
            loc = event_location(event)
            if loc:
                locations_changed.add(loc)
        
        turn_count = current_turn
        location_count = len(locations_changed)
        
        # 平均每 N 回合更换一次地点 (正常应为 10-30 回合)
        if turn_count > 0:
            avg_turns_per_location = turn_count / location_count if location_count > 0 else turn_count
            
            if avg_turns_per_location < 3:  # 过于频繁移动
                findings.append(Finding(
                    "WARNING", "对比一致性",
                    f"地点切换过于频繁：平均每{avg_turns_per_location:.1f}回合更换地点 (建议 10-30 回合)"
                ))
            elif avg_turns_per_location > 50 and turn_count > 20:  # 长时间未移动
                findings.append(Finding(
                    "INFO", "对比一致性",
                    f"长时间停留在单一地点：平均每{avg_turns_per_location:.1f}回合更换地点"
                ))
    
    # 6. 检查成就/解锁项与进度的关系
    achievements = player.get("achievements", [])
    unlocked_features = world.get("unlocked_features", [])
    
    # Turn 10 应该至少解锁 1-2 个成就
    if current_turn >= 10 and len(achievements) == 0:
        findings.append(Finding(
            "INFO", "对比一致性",
            f"当前回合 ({current_turn}) 但尚未获得任何成就 ({len(achievements)}条)"
        ))
    
    # 7. 检查技能数量与玩家等级的关系
    skills = player.get("skills", [])
    skill_count = len(skills)
    
    # 每 2 级获得约 1 个新技能的合理预期
    expected_skill_count = level // 2
    if skill_count < expected_skill_count * 0.5:
        findings.append(Finding(
            "WARNING", "对比一致性",
            f"技能数量 ({skill_count}) 偏少，建议至少{expected_skill_count}个 (按等级{level}推算)"
        ))
    
    return findings


def validate_public_system_consistency(save_dir, data):
    """九、公共系统一致性校验 - 确保经济、基建、公共服务的逻辑一致。"""
    findings = []
    
    base = data.get("base", {})
    inventory = data.get("inventory", {})
    world = data.get("world", {})
    events = data.get("events", [])
    
    # 1. 检查基地设施与可用资源的匹配
    facilities = base.get("facilities", {})
    resources = inventory.get("resources", {})
    
    required_resources_for_facilities = {
        "workshop": ["metal", "electricity"],
        "garden": ["water", "fertile_soil"],
        "clinic": ["medicine", "sterilization"],
        "power_plant": ["fuel", "maintenance_parts"],
        "defense_tower": ["steel", "ammunition"],
    }
    
    for facility_type, required_res in required_resources_for_facilities.items():
        if facilities.get(facility_type, {}).get("level", 0) > 0:
            for res in required_res:
                if not resources.get(res, 0) > 0 and not world.get("setting", {}).get("infinite_resources", False):
                    findings.append(Finding(
                        "WARNING", "公共系统一致性",
                        f"基地已建造 '{facility_type}'但未检测到必要资源 '{res}'"
                    ))
    
    # 2. 检查公共服务效率与服务对象的匹配
    services = base.get("services", {})
    npcs = data.get("npcs", [])
    active_npcs = [n for n in npcs if n.get("status") != "dead"]
    
    service_capacity = sum(s.get("capacity", 0) for s in services.values())
    population = len(active_npcs)
    
    if service_capacity > 0 and population > 0:
        coverage_ratio = service_capacity / population
        
        if coverage_ratio < 0.3:  # 覆盖率过低
            findings.append(Finding(
                "WARNING", "公共系统一致性",
                f"公共服务覆盖不足：服务能力({service_capacity})仅满足{coverage_ratio*100:.1f}%的人口 ({population})"
            ))
        elif coverage_ratio > 5.0:  # 过度建设
            findings.append(Finding(
                "WARNING", "公共系统一致性",
                f"公共服务过度冗余：服务能力({service_capacity})是人口的{coverage_ratio:.1f}倍"
            ))
    
    # 3. 检查经济系统的货币流通
    economy = world.get("economy", {})
    currency = economy.get("currency", {})
    player_cash = inventory.get("credits", 0)
    
    # 检查货币总量与物价水平的合理性
    price_index = economy.get("price_index", 1.0)
    if price_index > 10.0 and player_cash < 100:
        findings.append(Finding(
            "WARNING", "公共系统一致性",
            f"高物价环境 (价格指数={price_index}) 但玩家资金不足 ({player_cash})，可能存在生存压力"
        ))
    
    # 4. 检查市场供需平衡
    markets = economy.get("markets", {})
    for market_name, market_data in markets.items():
        supply = market_data.get("supply", 0)
        demand = market_data.get("demand", 0)
        
        if supply == 0 and demand > 0:
            findings.append(Finding(
                "INFO", "公共系统一致性",
                f"市场 '{market_name}'存在需求但无供给 (可能短缺)"
            ))
        elif supply > demand * 3:
            findings.append(Finding(
                "WARNING", "公共系统一致性",
                f"市场 '{market_name}'严重供过于求 (供应:{supply}, 需求:{demand})"
            ))
    
    # 5. 检查基础设施耐久度与维护
    infrastructure = base.get("infrastructure", {})
    maintenance_cost = base.get("monthly_maintenance", {})
    
    for infra_type, infra_data in infrastructure.items():
        durability = infra_data.get("durability", 100)
        
        if durability < 30:  # 耐久度低
            findings.append(Finding(
                "WARNING", "公共系统一致性",
                f"基础设施 '{infra_type}'耐久度仅剩 {durability}%，建议维修"
            ))
    
    # 6. 检查事件日志中的基建/维护记录
    infrastructure_events = [
        e for e in events 
        if any(kw in str(e.get("data", {})).lower() for kw in ["maintenance", "repair", "upgrade", "construction"])
    ]
    
    if infrastructure and len(infrastructure_events) == 0:
        findings.append(Finding(
            "INFO", "公共系统一致性",
            "存在基建数据但未检测到相关维护/升级记录"
        ))
    
    return findings


def validate_genre_consistency(save_dir, data):
    """十、流派一致性校验 - 确保内容符合废土列车主题设定的核心要素。"""
    findings = []
    
    world = data.get("world", {})
    setting = world.get("setting", {})
    story_text = data.get("story_text", "")
    event_log = data.get("event_log_text", "")
    
    # 1. 检查核心废土要素是否存在
    required_elements = {
        "safe_base": setting.get("safe_base"),
        "external_dangers": setting.get("external_dangers"),
        "exploration_method": setting.get("exploration_method"),
    }
    
    missing_elements = [k for k, v in required_elements.items() if not v]
    if missing_elements:
        findings.append(Finding(
            "CRITICAL", "流派一致性",
            f"缺失废土核心设定元素：{', '.join(missing_elements)}"
        ))
    
    # 2. 检查列车相关元素的保留
    train_elements = {
        "train_carriages": setting.get("train_carriages"),
        "engine_power": setting.get("engine_power"),
        "route_schedule": setting.get("route_schedule"),
    }
    
    # 根据世界观类型决定是否严格要求列车元素
    worldview = world.get("viewpoint", "third_person")
    is_train_world = "train" in worldview.lower() or "列车" in worldview
    
    if is_train_world:
        missing_train = [k for k, v in train_elements.items() if not v]
        if missing_train:
            findings.append(Finding(
                "ERROR", "流派一致性",
                f"列车世界观缺少关键元素：{', '.join(missing_train)}"
            ))
    
    # 3. 检查叙事文本中的关键词密度
    genre_keywords = {
        "survival": ["生存", "存活", "资源", "饥荒", "温饱"],
        "mystery": ["真相", "秘密", "线索", "阴谋", "遗迹"],
        "conflict": ["敌人", "威胁", "战斗", "对抗", "掠夺者"],
        "community": ["同伴", "伙伴", "团结", "组织", "派系"],
        "journey": ["旅途", "旅程", "前进", "抵达", "路线"],
    }
    
    text_content = story_text + "\n" + event_log
    
    keyword_density = {}
    for category, keywords in genre_keywords.items():
        count = sum(text_content.count(kw) for kw in keywords)
        keyword_density[category] = count
    
    # 检查各类别关键词是否至少有基本分布
    total_keyword_occurrences = sum(keyword_density.values())
    if total_keyword_occurrences > 0:
        survival_ratio = keyword_density["survival"] / total_keyword_occurrences
        
        if survival_ratio < 0.15:  # 生存主题占比过低
            findings.append(Finding(
                "WARNING", "流派一致性",
                "生存主题词汇占比偏低 (<15%)，可能偏离废土核心氛围"
            ))
    
    # 4. 检查敌对势力的多样性与威胁等级
    external_dangers = setting.get("external_dangers", [])
    
    if not external_dangers or len(external_dangers) < 2:
        findings.append(Finding(
            "WARNING", "流派一致性",
            f"外部威胁过少 ({len(external_dangers)}种)，建议至少 2-3 类不同性质的威胁"
        ))
    else:
        threat_types = set()
        for danger in external_dangers:
            if isinstance(danger, dict):
                threat_types.add(danger.get("type", danger.get("category", "unknown")))
        
        if len(threat_types) < 2:
            findings.append(Finding(
                "WARNING", "流派一致性",
                "外部威胁类型单一，建议增加多样性 (自然灾难/敌对势力/诡异现象等)"
            ))
    
    # 5. 检查科技水平与社会形态的一致性
    tech_level = setting.get("tech_level", "post_apocalyptic")
    social_form = setting.get("social_form", "scavenger_community")
    
    # 简单的规则检查
    high_tech_social_forms = ["cybernetic_society", "hive_mind", "digital_utopia"]
    low_tech_social_forms = ["tribal", "slavery", "dark_age"]
    
    if tech_level == "high" and social_form in low_tech_social_forms:
        findings.append(Finding(
            "WARNING", "流派一致性",
            "高科技水平与原始社会形态不匹配，建议调整设定一致性"
        ))
    
    # 6. 检查安全基地的可行性
    safe_base = setting.get("safe_base", "")
    
    if safe_base:
        # 检查是否有防御措施
        protection_measures = setting.get("protection_measures", [])
        
        if not protection_measures:
            findings.append(Finding(
                "WARNING", "流派一致性",
                f"安全基地 '{safe_base}' 缺少明确的防护措施配置"
            ))
        
        # 检查基地功能完备性
        base_functions = setting.get("base_functions", [])
        essential_functions = ["shelter", "resources", "safety", "communication"]
        
        missing_essential = [f for f in essential_functions if f not in base_functions]
        if missing_essential:
            findings.append(Finding(
                "WARNING", "流派一致性",
                f"基地功能不完整：缺少 {', '.join(missing_essential)} 等基本功能"
            ))
    
    # 7. 检查探索机制的合理性
    exploration_method = setting.get("exploration_method")
    
    if not exploration_method:
        findings.append(Finding(
            "ERROR", "流派一致性",
            "未定义探索方式，废土冒险缺乏基本探索机制"
        ))
    else:
        # 探索应该有代价和风险
        exploration_costs = setting.get("exploration_costs", {})
        
        if not exploration_costs:
            findings.append(Finding(
                "WARNING", "流派一致性",
                f"探索机制'{exploration_method}'缺少风险与代价配置"
            ))
    
    return findings


def validate_option_quality(save_dir, data):
    """十一、选项质量校验 - 确保待处理选项的质量与可用性。"""
    findings = []
    
    meta = data.get("meta", {})
    pending_options = meta.get("pending_options", {})
    
    # 1. 检查 pending_options 是否存在且有效
    if not pending_options:
        findings.append(Finding(
            "INFO", "选项质量",
            "当前无待处理选项 (可能是正常流程节点)"
        ))
        return findings
    
    options = pending_options.get("options", {})
    
    if not isinstance(options, dict) or not options:
        findings.append(Finding(
            "ERROR", "选项质量",
            "pending_options.options 为空或格式无效"
        ))
        return findings
    
    # 2. 检查选项数量合理性
    option_count = len(options)
    
    if option_count == 0:
        findings.append(Finding(
            "ERROR", "选项质量",
            "暂无可选方案可供玩家决策"
        ))
        return findings
    elif option_count > 6:
        findings.append(Finding(
            "WARNING", "选项质量",
            f"选项过多 ({option_count}个)，可能导致决策疲劳，建议控制在 3-6 个"
        ))
    elif option_count < 2:
        findings.append(Finding(
            "INFO", "选项质量",
            f"选项较少 ({option_count}个)，可能限制玩家选择空间"
        ))
    
    # 3. 检查每个选项的结构完整性
    for option_id, option in options.items():
        if not isinstance(option, dict):
            findings.append(Finding(
                "ERROR", "选项质量",
                f"选项 {option_id} 格式错误，不是对象类型"
            ))
            continue
        
        # 必填字段检查
        required_fields = ("label", "action", "description")
        missing_fields = [f for f in required_fields if f not in option]
        
        if missing_fields:
            findings.append(Finding(
                "ERROR", "选项质量",
                f"选项 {option_id} 缺少必需字段：{', '.join(missing_fields)}"
            ))
            continue
        
        # 检查 action 契约
        action = option.get("action", {})
        if not isinstance(action, dict):
            findings.append(Finding(
                "ERROR", "选项质量",
                f"选项 {option_id}.action 必须是对象"
            ))
        
        # 标签长度检查
        label = option.get("label", "")
        if len(label) > 50:
            findings.append(Finding(
                "WARNING", "选项质量",
                f"选项 {option_id} 标签过长 ({len(label)}字符)，建议简化到 50 字以内"
            ))
        elif len(label) < 5:
            findings.append(Finding(
                "INFO", "选项质量",
                f"选项 {option_id} 标签过短 ({len(label)}字符)，建议更明确"
            ))
        
        # 检查预览信息
        preview = option.get("preview", {})
        if not isinstance(preview, dict):
            findings.append(Finding(
                "WARNING", "选项质量",
                f"选项 {option_id} 缺少预览信息 (应是对象)"
            ))
        else:
            legal = preview.get("legal")
            
            # 必须有合法性验证
            if legal is not True:
                findings.append(Finding(
                    "ERROR", "选项质量",
                    f"选项 {option_id} 未通过合法性验证 (legal≠true)"
                ))
            
            # 检查是否有成本信息
            costs = preview.get("costs", {})
            if not costs:
                findings.append(Finding(
                    "WARNING", "选项质量",
                    f"选项 {option_id} 缺少行动成本说明"
                ))
    
    # 4. 检查选项多样性（避免同质化）
    action_types = set()
    for option_id, option in options.items():
        action = option.get("action", {})
        action_type = action.get("type", action.get("action_type", "unknown"))
        action_types.add(action_type)
    
    diversity_ratio = len(action_types) / option_count if option_count > 0 else 0
    
    if diversity_ratio < 0.5 and option_count >= 3:
        findings.append(Finding(
            "WARNING", "选项质量",
            f"选项重复度高：{len(action_types)}种类型/{option_count}个选项，建议增加差异化"
        ))
    
    # 5. 检查选项标签是否清晰区分
    labels = [opt.get("label", "") for opt in options.values()]
    similar_labels = []
    
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            if labels[i] and labels[j]:
                # 简单的相似度检查（共同词占比）
                common_words = set(labels[i].split()) & set(labels[j].split())
                if len(common_words) > 3:
                    similar_labels.append((labels[i], labels[j]))
    
    if similar_labels:
        findings.append(Finding(
            "WARNING", "选项质量",
            f"存在相似选项标签：{similar_labels[:3]}"
        ))
    
    # 6. 检查选项的时间敏感性
    state_turn = pending_options.get("state_turn", 0)
    current_turn = meta.get("current_turn", 0)
    
    if state_turn != current_turn:
        findings.append(Finding(
            "WARNING", "选项质量",
            f"选项状态回合 ({state_turn}) 与当前回合 ({current_turn}) 不一致"
        ))
    
    # 7. 检查是否有默认选项标记
    default_option = pending_options.get("default_option")
    
    if option_count > 3 and not default_option:
        findings.append(Finding(
            "INFO", "选项质量",
            "多个选项但无默认推荐，建议设置 default_option 指引新手"
        ))
    
    return findings


# ─── 主流程 ─────────────────────────────────────────────────

def _load_validation_data(save_dir):
    """加载一次完整校验输入；启动门禁与人类报告共用同一套事实。"""
    world_package = load_yaml(save_dir / "world.yaml") or {}
    data = {
        "meta": (load_yaml(save_dir / "meta.yaml") or {}).get("meta", {}),
        "world": world_package.get("world", {}),
        "player_talent": world_package.get("player_talent", {}),
        "player": (load_yaml(save_dir / "player.yaml") or {}).get("player", {}),
        "base": (load_yaml(save_dir / "base.yaml") or {}).get("base", {}),
        "inventory": (load_yaml(save_dir / "inventory.yaml") or {}).get("inventory", {}),
        "npcs": (load_yaml(save_dir / "npcs.yaml") or {}).get("npcs", []),
        "factions": (load_yaml(save_dir / "factions.yaml") or {}).get("factions", []),
        "relationships": (load_yaml(save_dir / "relationships.yaml") or {}).get("relationships", {}),
        "event_queue": (load_yaml(save_dir / "event_queue.yaml") or {}).get("event_queue", []),
        "region_state": (load_yaml(save_dir / "region_state.yaml") or {}).get("region_state", {}),
        "population_state": (load_yaml(save_dir / "population_state.yaml") or {}).get("population_state", {}),
        "public_system_state": (load_yaml(save_dir / "public_system_state.yaml") or {}).get("public_system_state", {}),
        "market_state": (load_yaml(save_dir / "market_state.yaml") or {}).get("market_state", {}),
        "ranking_state": (load_yaml(save_dir / "ranking_state.yaml") or {}).get("ranking_state", {}),
        "comparative_state": (load_yaml(save_dir / "comparative_state.yaml") or {}).get("comparative_state", {}),
        "rival_state": (load_yaml(save_dir / "rival_state.yaml") or {}).get("rival_state", {}),
        "event_log_text": load_text(save_dir / "event_log.md"),
        "story_text": load_text(save_dir / "story.md"),
    }
    data["events"], data["event_parse_errors"] = parse_event_blocks(data["event_log_text"])
    campaign_path = save_dir / "campaign.sqlite3"
    if campaign_path.exists():
        try:
            from engine_runtime.persistence import SQLiteEventStore

            sql_records = SQLiteEventStore(campaign_path).events()
            data["events"] = [{"turn": int(record.get("turn", 0)), "data": record, "text": json.dumps(record, ensure_ascii=False)} for record in sql_records]
            data["event_parse_errors"] = []
        except (OSError, ValueError, RuntimeError) as exc:
            data["event_parse_errors"] = [f"SQLite 事件读取失败：{exc}"]
    return data


def collect_findings(save_path):
    save_dir = Path(save_path)
    if not save_dir.is_dir():
        raise ValueError(f"找不到存档目录：{save_path}")
    data = _load_validation_data(save_dir)
    all_findings = []
    all_findings.extend(validate_world_package(save_dir, data))
    all_findings.extend(validate_event_sourcing(save_dir, data))
    all_findings.extend(validate_action_economy(save_dir, data))
    all_findings.extend(validate_formula_trace(save_dir, data))
    all_findings.extend(validate_continuity(save_dir, data))
    all_findings.extend(validate_rules(save_dir, data))
    all_findings.extend(validate_knowledge(save_dir, data))
    all_findings.extend(validate_combat(save_dir, data))
    all_findings.extend(validate_relationships(save_dir, data))
    all_findings.extend(validate_narrative(save_dir, data))
    # 新增五项校验
    all_findings.extend(validate_population_consistency(save_dir, data))
    all_findings.extend(validate_comparative_consistency(save_dir, data))
    all_findings.extend(validate_public_system_consistency(save_dir, data))
    all_findings.extend(validate_genre_consistency(save_dir, data))
    all_findings.extend(validate_option_quality(save_dir, data))
    return all_findings


def assert_startable(save_path):
    """启动硬门禁：CRITICAL/ERROR 都不能进入游戏流程。"""
    findings = collect_findings(save_path)
    blockers = [finding for finding in findings if finding.severity in {"CRITICAL", "ERROR"}]
    if blockers:
        summary = "；".join(f"[{item.severity}] {item.message}" for item in blockers[:6])
        raise ValueError(f"存档启动门禁拒绝继续：{summary}")
    return findings


def run_validation(save_path):
    save_dir = Path(save_path)
    try:
        all_findings = collect_findings(save_path)
    except ValueError as exc:
        print(f"错误：{exc}")
        return 1

    print(f"═══ 校验存档：{save_dir.name} ═══\n")

    # 按严重度分组输出

    # 按严重度分组输出
    severity_order = ["CRITICAL", "ERROR", "WARNING", "INFO"]
    for sev in severity_order:
        group = [f for f in all_findings if f.severity == sev]
        if group:
            print(f"\n{'━' * 50}")
            print(f"  {sev} ({len(group)})")
            print(f"{'━' * 50}")
            for f in group:
                print(f"  [{f.category}] {f.message}")

    # 总结
    print(f"\n{'═' * 50}")
    total = len(all_findings)
    critical = len([f for f in all_findings if f.severity == "CRITICAL"])
    errors = len([f for f in all_findings if f.severity == "ERROR"])
    warnings = len([f for f in all_findings if f.severity == "WARNING"])
    infos = len([f for f in all_findings if f.severity == "INFO"])

    print(f"  总计: {total} 项")
    print(f"  CRITICAL: {critical} | ERROR: {errors} | WARNING: {warnings} | INFO: {infos}")

    if critical > 0:
        print(f"\n  ⚠ 存在 CRITICAL 级别问题，必须修复后才能继续游戏。")
    elif errors > 0:
        print(f"\n  ⚡ 存在 ERROR 级别问题，建议修复。")
    elif warnings > 0:
        print(f"\n  ✓ 无严重问题，有 {warnings} 条建议。")
    else:
        print(f"\n  ✓ 全部通过，存档状态健康。")

    print(f"{'═' * 50}")
    return 0 if critical == 0 and errors == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python validate_save.py <存档路径>")
        print("示例: python validate_save.py saves/渊驮")
        sys.exit(1)

    exit_code = run_validation(sys.argv[1])
    sys.exit(exit_code)
