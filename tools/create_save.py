#!/usr/bin/env python3
"""根据世界创建问卷生成一个可校验的新游戏存档。

用法：
    python tools/create_save.py --answers answers.yaml
    python tools/create_save.py --interactive

answers.yaml 可以是 world.yaml 形状的文件：
    world: {...}
    player_talent: {...}

脚本只会创建不存在的存档目录，绝不覆盖已有世界。
"""

import argparse
import copy
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("需要 PyYAML: pip install pyyaml")
    sys.exit(1)

from validate_save import run_validation


DIFFICULTIES = {"休闲", "标准", "硬核"}
DEATH_MODES = {"permanent", "checkpoint", "legacy"}
REQUIRED_QUESTIONS = (
    ("theme", "世界主题", "永夜冰川"),
    ("safe_base", "玩家的安全基地", "不断行驶的雪地列车"),
    ("external_dangers", "外部主要危险（用逗号分隔）", "冰尸、极寒、燃料不足"),
    ("primary_resources", "最重要的基础资源（3-5种，用逗号分隔）", "煤炭、食物、寒晶"),
    ("talent", "主角的特殊天赋名称", "预兆回响"),
    ("exploration_method", "玩家通过什么方式探索", "列车停车时下车搜索"),
    ("disaster_cycle", "每隔多久发生一次大型灾难", "每七天一次白夜风暴"),
    ("difficulty", "游戏残酷程度（休闲/标准/硬核）", "标准"),
    ("narrative_length", "每段叙述长度（1-10）", "7"),
    ("language", "游戏语言（留空为中文）", "中文"),
)


class GeneratorError(ValueError):
    """输入不符合新游戏契约。"""


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise GeneratorError(f"{path} 顶层必须是 YAML 对象")
    return value


def write_yaml(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(value, handle, allow_unicode=True, sort_keys=False)


def deep_merge(base, override):
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def split_items(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,，、;；]", value) if item.strip()]
    if isinstance(value, list):
        return value
    return [value]


def item_name(item):
    if isinstance(item, dict):
        return str(item.get("name", "")).strip()
    return str(item).strip()


def normalize_resource_items(items):
    normalized = []
    for item in split_items(items):
        if isinstance(item, dict):
            record = copy.deepcopy(item)
            record["name"] = item_name(item)
        else:
            record = {"name": item_name(item), "description": ""}
        if record["name"]:
            normalized.append(record)
    return normalized


def first_number(value):
    match = re.search(r"\d+", str(value or ""))
    return int(match.group(0)) if match else None


def safe_world_name(name):
    name = str(name or "").strip()
    if not name:
        raise GeneratorError("世界名称不能为空")
    if name in {".", ".."} or ".." in name:
        raise GeneratorError("世界名称不能包含 '..'")
    if Path(name).name != name or re.search(r'[<>:"/\\|?*]', name):
        raise GeneratorError("世界名称包含 Windows 不允许的路径字符")
    if name.endswith((".", " ")):
        raise GeneratorError("世界名称不能以句点或空格结尾")
    if name.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL"}:
        raise GeneratorError("世界名称不能使用 Windows 保留设备名")
    return name


def infer_death_mode(difficulty):
    return "permanent" if difficulty == "硬核" else "checkpoint"


def infer_base_type(name):
    lowered = name.lower()
    if "列车" in name or "train" in lowered:
        return "train"
    if "木筏" in name or "raft" in lowered:
        return "raft"
    if "巨兽" in name or "beast" in lowered:
        return "beast"
    if "缆车" in name or "cable" in lowered:
        return "cable_car"
    return "other"


def prompt_world():
    print("创建你的世界（先输入世界名称；之后是 AGENTS.md 规定的10问）：")
    world_name = input("世界名称（留空则取主题）：").strip()
    answers = {}
    for key, label, example in REQUIRED_QUESTIONS:
        raw = input(f"{label}（例：{example}）：").strip()
        if key == "difficulty" and not raw:
            raw = "标准"
        if key == "language" and not raw:
            raw = "中文"
        answers[key] = raw

    if not world_name:
        world_name = re.sub(r'[<>:"/\\|?*]', "", answers["theme"]).replace("..", "").strip()
        world_name = world_name[:32] or "新世界"
    talent_name = answers["talent"]
    answers["world_name"] = world_name
    answers["player_talent"] = {
        "name": talent_name,
        "description": f"围绕“{talent_name}”展开的初始天赋。",
        "type": "信息类",
        "trigger": "满足天赋规则时",
        "effect": "由规则引擎按具体效果结算",
        "limitations": "效果受世界规则、冷却与资源限制",
    }
    return answers


def answers_to_package(raw):
    """接受完整 world.yaml，也接受较扁平的问卷答案对象。"""
    if "answers" in raw and isinstance(raw["answers"], dict):
        raw = raw["answers"]
    if isinstance(raw.get("world"), dict):
        world = copy.deepcopy(raw["world"])
        talent = copy.deepcopy(raw.get("player_talent", {}))
        return world, talent

    world = {
        "name": raw.get("world_name", raw.get("name", "")),
        "theme": raw.get("theme", ""),
        "difficulty": raw.get("difficulty", "标准"),
        "narrative_length": raw.get("narrative_length", 7),
        "language": raw.get("language", "中文"),
        "setting": {
            "safe_base": raw.get("safe_base", ""),
            "external_dangers": raw.get("external_dangers", []),
            "exploration_method": raw.get("exploration_method", ""),
            "disaster_cycle": raw.get("disaster_cycle", ""),
            "disaster_type": raw.get("disaster_type", ""),
        },
        "resources": {"primary": raw.get("primary_resources", raw.get("resources", []))},
    }
    talent = copy.deepcopy(raw.get("player_talent", raw.get("talent", {})))
    if isinstance(talent, str):
        talent = {"name": talent}
    return world, talent


def normalize_package(template, supplied_world, supplied_talent, world_name_override=None):
    world = deep_merge(template["world"], supplied_world)
    talent = deep_merge(template.get("player_talent", {}), supplied_talent)

    if world_name_override:
        world["name"] = world_name_override
    world["name"] = safe_world_name(world.get("name"))
    world["theme"] = str(world.get("theme", "")).strip()
    world["narrative_style"] = world.get("narrative_style") or "冷酷"
    world["difficulty"] = str(world.get("difficulty", "")).strip()
    world["language"] = str(world.get("language") or "中文").strip()

    try:
        world["narrative_length"] = int(world.get("narrative_length", 7))
    except (TypeError, ValueError) as exc:
        raise GeneratorError("narrative_length 必须是1到10的整数") from exc

    setting = world.setdefault("setting", {})
    setting["safe_base"] = str(setting.get("safe_base", "")).strip()
    setting["external_dangers"] = split_items(setting.get("external_dangers"))
    setting["exploration_method"] = str(setting.get("exploration_method", "")).strip()
    setting["disaster_cycle"] = str(setting.get("disaster_cycle", "")).strip()
    setting["disaster_type"] = str(setting.get("disaster_type") or "大型灾难").strip()

    resources = world.setdefault("resources", {})
    resources["primary"] = normalize_resource_items(resources.get("primary"))
    resources["secondary"] = normalize_resource_items(resources.get("secondary"))
    resources["rare"] = normalize_resource_items(resources.get("rare"))
    resources["currency"] = str(resources.get("currency") or "交易筹码").strip()

    cycle_days = first_number(setting["disaster_cycle"])
    if cycle_days is None:
        cycle_days = first_number(world.get("rules", {}).get("disaster", {}).get("cycle_days"))
    if cycle_days is None or cycle_days < 1:
        raise GeneratorError("灾难周期必须包含一个正整数天数")
    disaster_rules = world.setdefault("rules", {}).setdefault("disaster", {})
    disaster_rules["cycle_days"] = cycle_days
    disaster_rules["first_event"] = disaster_rules.get("first_event") or f"第{cycle_days}天"
    death_rules = world["rules"].setdefault("death", {})
    death_rules["type"] = death_rules.get("type") or infer_death_mode(world["difficulty"])

    talent = talent or {}
    talent["name"] = str(talent.get("name", "")).strip()
    for field in ("description", "type", "trigger", "effect", "limitations"):
        talent[field] = str(talent.get(field, "")).strip()

    if not world["theme"]:
        raise GeneratorError("世界主题不能为空")
    if not setting["safe_base"]:
        raise GeneratorError("安全基地不能为空")
    if not setting["external_dangers"]:
        raise GeneratorError("外部主要危险至少需要一项")
    if not setting["exploration_method"]:
        raise GeneratorError("探索方式不能为空")
    if world["difficulty"] not in DIFFICULTIES:
        raise GeneratorError("difficulty 必须是：休闲、标准或硬核")
    if not 1 <= world["narrative_length"] <= 10:
        raise GeneratorError("narrative_length 必须在1到10之间")
    if not 3 <= len(resources["primary"]) <= 5:
        raise GeneratorError("基础资源必须是3到5种")
    if not talent["name"] or any(not talent[field] for field in ("description", "type", "trigger", "effect", "limitations")):
        raise GeneratorError("主角天赋必须填写 name/description/type/trigger/effect/limitations")
    if death_rules["type"] not in DEATH_MODES:
        raise GeneratorError("rules.death.type 必须是 permanent/checkpoint/legacy")
    return world, talent


def build_files(template_dir, world, talent):
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    setting = world["setting"]
    world_name = world["name"]
    safe_base = setting["safe_base"]
    phase = (world.get("phases") or [{"name": "新手期"}])[0].get("name", "新手期")
    mysteries = [
        item.get("question", str(item)) if isinstance(item, dict) else str(item)
        for item in world.get("mysteries", [])[:5]
    ]
    primary_resources = world["resources"]["primary"]

    files = {}
    files["world.yaml"] = {"world": world, "player_talent": talent}
    files["player.yaml"] = {
        "player": {
            "name": "未命名主角",
            "gender": "",
            "age": "",
            "background": "",
            "level": 1,
            "exp": 0,
            "exp_to_next": 100,
            "attributes": {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5},
            "free_points": 4,
            "hp": 50,
            "max_hp": 50,
            "status_effects": [],
            "hunger": 100,
            "fatigue": 0,
            "mental": 100,
            "max_mental": 100,
            "talents": [{**talent, "rarity": "custom", "obtained_turn": 1}],
            "skills": [],
            "class": None,
            "second_class": None,
            "personality": {"caution": 50, "ambition": 50, "empathy": 50, "honesty": 50, "risk_tolerance": 50, "collectivism": 50},
            "achievements": [],
            "stats": {"kills": 0, "deaths": 0, "explorations": 0, "crafts": 0, "trades": 0},
        }
    }
    files["base.yaml"] = {
        "base": {
            "name": safe_base,
            "type": infer_base_type(safe_base),
            "level": 1,
            "durability": 100,
            "max_durability": 100,
            "defense": 10,
            "space_total": 3,
            "space_used": 0,
            "modules": [],
            "special_properties": [f"安全基地：{safe_base}"],
            "cohabitants": [],
            "defense_log": [],
        }
    }
    files["inventory.yaml"] = {
        "inventory": {
            "equipment": {"main_weapon": None, "off_hand": None, "helmet": None, "chest": None, "legs": None, "boots": None, "accessory_1": None, "accessory_2": None},
            "items": [],
            "resources": {item["name"]: 0 for item in primary_resources},
            "weight_current": 0,
            "weight_max": 50,
            "currency": 0,
        }
    }
    files["npcs.yaml"] = {"npcs": []}
    files["factions.yaml"] = {"factions": []}
    files["relationships.yaml"] = {"relationships": []}
    files["event_queue.yaml"] = {"event_queue": []}
    files["meta.yaml"] = {
        "meta": {
            "save_name": f"{world_name}·第一日",
            "world_name": world_name,
            "created_at": now,
            "current_turn": 1,
            "game_day": 1,
            "time_of_day": "清晨",
            "phase": phase,
            "difficulty": world["difficulty"],
            "death_mode": world["rules"]["death"]["type"],
            "narrative_length": world["narrative_length"],
            "language": world["language"],
            "event_format_version": 2,
            "created_by": "tools/create_save.py",
            "rng_seed": world_name,
            "runtime_metrics": {},
            "checkpoints_used": 0,
            "max_checkpoints": 3,
            "current_location": safe_base,
            "current_mode": "base",
            "in_combat": False,
            "pressure_level": 30,
            "last_payoff_turn": 0,
            "active_mysteries": mysteries,
            "foreshadowing_active": [],
            "total_decisions": 0,
            "total_combats": 0,
            "total_explorations": 0,
            "npcs_met": 0,
            "factions_encountered": 0,
            "last_played": now,
            "last_session_turns": 0,
            "recap_needed": False,
        }
    }
    event_data = {
        "event_id": "evt_0001_001",
        "type": "WORLD_CREATED",
        "actor": "system",
        "target": None,
        "data": {"world_name": world_name, "theme": world["theme"], "safe_base": safe_base, "difficulty": world["difficulty"]},
        "turn": 1,
        "timestamp": "Day 1 清晨",
    }
    event_log = "# 事件日志\n\n<!-- 由 tools/create_save.py 创建；后续事件使用标准事件格式。 -->\n\n---\n## Turn 1 | Day 1 清晨 | 世界创建\n```json\n" + json.dumps([event_data], ensure_ascii=False, indent=2) + "\n```\n"
    story = "\n".join([
        "# 故事摘要",
        "",
        "## 当前处境",
        f"世界“{world_name}”以“{world['theme']}”为核心。主角在{safe_base}中醒来，基地暂时安全，但外部存在" + "、".join(setting["external_dangers"]) + "。",
        "",
        "## 关键事件",
        "Day 1：系统完成世界初始化，主角获得初始天赋，尚未进行第一次正式行动。",
        "",
        "## 未解悬念",
        *(f"- {mystery}" for mystery in mysteries),
        "",
        "## 重要NPC动态",
        "当前尚未遇到重要NPC；后续NPC必须按自身目标和日程行动。",
        "",
        "## 下一步方向",
        f"围绕{setting['exploration_method']}制定第一个行动方案；基础资源包括" + "、".join(item["name"] for item in primary_resources) + "。",
    ]) + "\n"
    files["event_log.md"] = event_log
    files["story.md"] = story
    files["novel_draft.md"] = f"# 《{world_name}》\n"
    files["conversation_log.md"] = f"# 《{world_name}》对话记录\n"
    files["decision_audit.jsonl"] = ""
    files["decision_audit.md"] = "# 决策审计\n"
    return files


def create_save(args):
    project_dir = Path(__file__).resolve().parent.parent
    template_dir = project_dir / "templates" / "save_template"
    template_world_path = project_dir / "templates" / "world_template.yaml"
    save_root = Path(args.save_root).resolve()
    save_root.mkdir(parents=True, exist_ok=True)

    template = load_yaml(template_world_path)
    if args.answers:
        raw = load_yaml(Path(args.answers))
    else:
        raw = prompt_world()
    supplied_world, supplied_talent = answers_to_package(raw)
    world, talent = normalize_package(template, supplied_world, supplied_talent, args.world_name)

    target = (save_root / world["name"]).resolve()
    if target.parent != save_root:
        raise GeneratorError("生成路径超出 save_root")
    if target.exists():
        raise GeneratorError(f"存档已存在，不覆盖：{target}")

    target.mkdir()
    try:
        for source in template_dir.iterdir():
            destination = target / source.name
            if source.is_file():
                shutil.copy2(source, destination)
        files = build_files(template_dir, world, talent)
        for filename, content in files.items():
            destination = target / filename
            if filename.endswith((".yaml", ".yml")):
                write_yaml(destination, content)
            else:
                with open(destination, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(content)

        result = run_validation(str(target))
        if result != 0:
            raise GeneratorError(f"新存档未通过校验，已回滚：{target}")
    except Exception:
        if target.exists() and target.parent == save_root:
            shutil.rmtree(target)
        raise

    print(f"新游戏已创建并通过校验：{target}")
    return target


def main():
    parser = argparse.ArgumentParser(description="生成并校验 TheGreatNovel 新游戏存档")
    parser.add_argument("--answers", help="完整 world.yaml 或问卷答案 YAML 文件")
    parser.add_argument("--interactive", action="store_true", help="交互式回答世界创建问题")
    parser.add_argument("--world-name", help="覆盖答案中的世界名称")
    parser.add_argument("--save-root", default="saves", help="存档根目录，默认 saves")
    args = parser.parse_args()
    if args.answers and args.interactive:
        parser.error("--answers 与 --interactive 不能同时使用")
    if not args.answers and not args.interactive:
        args.interactive = True
    try:
        create_save(args)
    except (GeneratorError, OSError, yaml.YAMLError) as exc:
        print(f"创建失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
