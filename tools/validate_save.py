#!/usr/bin/env python3
"""
TheGreatNovel 存档校验器
实现 engine/validators.md 中定义的六类校验。

用法：
    python validate_save.py <存档路径>
    python validate_save.py saves/渊驮

输出：按严重度分组的校验结果（CRITICAL / ERROR / WARNING / INFO）
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
    if generation.get("mechanics_source") == "theme_profile":
        bundle = world.get("generation_bundle")
        required_bundle = ("starting_location", "locations", "enemies", "areas", "build_catalog", "action_targets", "starting_inventory", "starting_npcs", "starting_factions", "starting_relationships")
        if not isinstance(bundle, dict):
            findings.append(Finding("CRITICAL", "规则", "主题世界缺少 generation_bundle"))
        else:
            missing_bundle = [field for field in required_bundle if not bundle.get(field)]
            if missing_bundle:
                findings.append(Finding("CRITICAL", "规则", f"generation_bundle 缺少可执行字段：{', '.join(missing_bundle)}"))
            if str(bundle.get("compiler_version", "")) != str(COMPILER_VERSION):
                findings.append(Finding("CRITICAL", "规则", f"generation_bundle.compiler_version={bundle.get('compiler_version')} 与当前编译器 {COMPILER_VERSION} 不兼容"))
            location_values = bundle.get("locations", [])
            location_ids = {
                str(item.get("id", item.get("name"))) for item in location_values
                if isinstance(item, dict) and item.get("id", item.get("name"))
            } if isinstance(location_values, list) else {str(key) for key in location_values} if isinstance(location_values, dict) else set()
            if current_location and not registered_location_ids and str(current_location) not in location_ids:
                findings.append(Finding("CRITICAL", "连续性", f"meta.current_location 未注册：{current_location}"))
        if not (save_dir / "campaign.sqlite3").exists():
            findings.append(Finding("CRITICAL", "连续性", "主题世界缺少 SQLite 事件存储 campaign.sqlite3"))
        else:
            try:
                from engine_runtime.events import apply_event
                from engine_runtime.persistence import SQLiteEventStore

                store = SQLiteEventStore(save_dir / "campaign.sqlite3")
                projection = store.verify_projection(apply_event)
                if not projection.get("ok"):
                    findings.append(Finding("CRITICAL", "连续性", "SQLite 事件重放结果与最新投影不一致"))
                snapshot = store.latest_snapshot() or {}
                view_keys = ("world", "player", "base", "inventory", "npcs", "factions", "relationships", "event_queue", "meta", "player_talent")
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
    engine_event_types = {"ACTION_RESOLVED", "EXPLORATION_RESOLVED", "RESEARCH_RESOLVED", "SOCIAL_RESOLVED", "COMBAT_RESOLVED", "BATCH_ACTION_RESOLVED", "BUILDING_BUILT", "BASE_MAINTENANCE"}
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
