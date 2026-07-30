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
import random
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

try:
    import yaml
except ImportError:
    print("需要 PyYAML: pip install pyyaml")
    sys.exit(1)

try:
    from validate_save import run_validation
except ModuleNotFoundError:  # 支持从项目根目录 import tools.create_save
    from tools.validate_save import run_validation

from engine_runtime.world_compiler import compile_world_bundle
from engine_runtime.state import load_game_state


DIFFICULTIES = {"休闲", "标准", "硬核"}
DEATH_MODES = {"permanent", "checkpoint", "legacy"}
REQUIRED_QUESTIONS = (
    ("theme", "世界主题", "永夜冰川 / 巨兽背部 / 废土列车 / 深渊裂隙；也可自定义"),
    ("difficulty", "游戏残酷程度", "1=休闲，2=标准，3=硬核永久死亡"),
    ("narrative_length", "每段叙述长度（1-10）", "1=极短，5=中等，7=标准，10=极长"),
    ("language", "游戏语言", "1=中文，2=English，3=日本語；留空为中文"),
)


# 世界运行机制不是让玩家凭空填写的问卷答案，而是由主题映射得到。
# 每个主题档案都必须同时给出基地、危险、资源、天赋、探索方式和灾难周期，
# 这样同一主题在交互式创建和 YAML 创建中会得到同一套初始逻辑。
WORLD_MECHANIC_PROFILES = (
    {
        "id": "永夜冰川",
        "keywords": ("永夜", "冰川", "极寒", "冰雪", "雪原", "冻土"),
        "zh": {
            "safe_base": "霜轨列车",
            "external_dangers": ["冰尸", "极寒", "燃料枯竭"],
            "primary_resources": ["煤炭", "食物", "寒晶"],
            "exploration_method": "列车停车后的安全窗口内下车搜索",
            "disaster_cycle": "每七天一次白夜风暴",
            "disaster_type": "白夜风暴",
            "talent": {
                "name": "寒潮预兆",
                "description": "能够在短时间内感知附近极寒灾变的先兆。",
                "type": "信息类",
                "trigger": "进入新的冰雪区域或灾难倒计时进入预警期时",
                "effect": "提前获得有限的环境危险提示",
                "limitations": "提示不完整，且受疲劳与精神状态影响",
            },
        },
        "en": {
            "safe_base": "Frostrail Train",
            "external_dangers": ["Ice Dead", "Extreme Cold", "Fuel Depletion"],
            "primary_resources": ["Coal", "Food", "Cryo Crystals"],
            "exploration_method": "Search outside the train during a safe stopping window",
            "disaster_cycle": "A White-Night Storm every seven days",
            "disaster_type": "White-Night Storm",
            "talent": {
                "name": "Coldfront Premonition",
                "description": "Senses early signs of nearby cold-related disasters.",
                "type": "Information",
                "trigger": "Entering a new icy region or reaching a disaster warning window",
                "effect": "Provides limited advance warnings about environmental hazards.",
                "limitations": "Warnings are incomplete and affected by fatigue and mental state.",
            },
        },
    },
    {
        "id": "巨兽背部",
        "keywords": ("巨兽", "背部", "兽背", "巨兽背"),
        "zh": {
            "safe_base": "巨兽背部的移动营地",
            "external_dangers": ["巨兽翻身", "寄生兽群", "食物短缺"],
            "primary_resources": ["肉干", "骨材", "生命晶核"],
            "exploration_method": "沿巨兽背部的索具和脊骨向未知区域搜索",
            "disaster_cycle": "每五天一次巨兽迁徙暴动",
            "disaster_type": "巨兽迁徙暴动",
            "talent": {
                "name": "脊动感知",
                "description": "能够从脚下震动判断巨兽的情绪和即将发生的动作。",
                "type": "信息类",
                "trigger": "站在巨兽背部或其延伸结构上时",
                "effect": "提前发现部分翻身、冲撞和迁徙征兆",
                "limitations": "无法读取巨兽的完整意图，且在战斗中容易被噪声干扰",
            },
        },
        "en": {
            "safe_base": "A Moving Camp on the Behemoth's Back",
            "external_dangers": ["Behemoth Rolls", "Parasite Swarms", "Food Shortage"],
            "primary_resources": ["Dried Meat", "Bone Material", "Vital Cores"],
            "exploration_method": "Search unknown regions along the behemoth's rigging and spine",
            "disaster_cycle": "A Migration Rampage every five days",
            "disaster_type": "Migration Rampage",
            "talent": {
                "name": "Spine Sense",
                "description": "Reads the behemoth's mood and imminent movements through vibrations.",
                "type": "Information",
                "trigger": "Standing on the behemoth's back or its extensions",
                "effect": "Detects some early signs of rolls, impacts, and migrations.",
                "limitations": "Cannot read the behemoth's full intent and is disrupted by combat noise.",
            },
        },
    },
    {
        "id": "废土列车",
        "keywords": ("废土", "末日", "荒原", "列车", "辐射"),
        "zh": {
            "safe_base": "不断行驶的废土列车",
            "external_dangers": ["掠夺者", "辐射尘暴", "燃料不足"],
            "primary_resources": ["燃油", "净水", "废旧金属"],
            "exploration_method": "列车停靠时下车搜索并在发车前撤离",
            "disaster_cycle": "每六天一次辐射尘暴",
            "disaster_type": "辐射尘暴",
            "talent": {
                "name": "危险预兆",
                "description": "能够从微弱的声音、气味和光线变化中识别附近危险。",
                "type": "信息类",
                "trigger": "进入未侦察的废土地点时",
                "effect": "获得一次关于主要威胁方向的有限提示",
                "limitations": "提示不能直接揭示敌人数量、战力或完整伏击方案",
            },
        },
        "en": {
            "safe_base": "The Ever-Moving Wasteland Train",
            "external_dangers": ["Raiders", "Radiation Duststorms", "Fuel Shortage"],
            "primary_resources": ["Fuel", "Purified Water", "Scrap Metal"],
            "exploration_method": "Search during train stops and retreat before departure",
            "disaster_cycle": "A Radiation Duststorm every six days",
            "disaster_type": "Radiation Duststorm",
            "talent": {
                "name": "Danger Premonition",
                "description": "Recognizes nearby danger through subtle changes in sound, smell, and light.",
                "type": "Information",
                "trigger": "Entering an unscouted wasteland location",
                "effect": "Provides one limited hint about the direction of the main threat.",
                "limitations": "Cannot reveal enemy count, strength, or the full ambush plan.",
            },
        },
    },
    {
        "id": "深渊裂隙",
        "keywords": ("深渊", "裂隙", "地底", "虚空", "深层"),
        "zh": {
            "safe_base": "裂隙边缘的升降基地",
            "external_dangers": ["裂隙潮汐", "深渊生物", "精神污染"],
            "primary_resources": ["稳定晶核", "净化药剂", "锚定材料"],
            "exploration_method": "通过升降平台进入裂隙层并沿锚点推进",
            "disaster_cycle": "每三天一次裂隙潮汐",
            "disaster_type": "裂隙潮汐",
            "talent": {
                "name": "裂隙回声",
                "description": "能够听见裂隙中即将发生的局部变化。",
                "type": "信息类",
                "trigger": "靠近新的裂隙层或不稳定锚点时",
                "effect": "获得关于空间变化或精神污染的预警",
                "limitations": "回声可能混入旧事件，必须结合现场证据判断",
            },
        },
        "en": {
            "safe_base": "The Lift Base at the Rift's Edge",
            "external_dangers": ["Rift Tides", "Abyssal Creatures", "Mental Contamination"],
            "primary_resources": ["Stable Cores", "Purifying Agents", "Anchoring Material"],
            "exploration_method": "Descend through lift platforms and advance between anchors",
            "disaster_cycle": "A Rift Tide every three days",
            "disaster_type": "Rift Tide",
            "talent": {
                "name": "Rift Echo",
                "description": "Hears local changes that are about to occur within the rift.",
                "type": "Information",
                "trigger": "Approaching a new rift layer or unstable anchor",
                "effect": "Warns of spatial changes or mental contamination.",
                "limitations": "Echoes may contain old events and must be checked against evidence.",
            },
        },
    },
)


GENERIC_WORLD_MECHANICS = {
    "id": "generic",
    "zh": {
        "safe_base": "围绕主题建立的移动避难所",
        "external_dangers": ["未知生物", "环境灾害", "基础资源枯竭"],
        "primary_resources": ["食物", "工具材料", "核心能源"],
        "exploration_method": "在安全窗口内离开基地搜索并按时撤回",
        "disaster_cycle": "每七天一次大型灾难",
        "disaster_type": "大型环境灾难",
        "talent": {
            "name": "危险预兆",
            "description": "能够感知附近环境中不寻常的变化。",
            "type": "信息类",
            "trigger": "进入新的未知区域时",
            "effect": "获得一条有限的危险提示",
            "limitations": "提示不完整，不能替代侦察和规则结算",
        },
    },
    "en": {
        "safe_base": "A Mobile Shelter Built Around the Theme",
        "external_dangers": ["Unknown Creatures", "Environmental Disasters", "Depleting Supplies"],
        "primary_resources": ["Food", "Tool Materials", "Core Energy"],
        "exploration_method": "Leave the shelter during safe windows, search, and return on time",
        "disaster_cycle": "A Major Disaster every seven days",
        "disaster_type": "Major Environmental Disaster",
        "talent": {
            "name": "Danger Premonition",
            "description": "Senses unusual changes in the nearby environment.",
            "type": "Information",
            "trigger": "Entering a new unknown region",
            "effect": "Provides one limited danger warning.",
            "limitations": "Warnings are incomplete and cannot replace scouting or rule resolution.",
        },
    },
}


class GeneratorError(ValueError):
    """输入不符合新游戏契约。"""


def generate_world_mechanics(theme, language="中文"):
    """根据主题确定性生成六项运行机制。

    这是世界创建的唯一默认来源：交互式问卷不要求玩家填写这些字段，
    但完整 YAML 仍可显式覆盖单个字段，便于高级用户制作自定义世界。
    """
    theme = str(theme or "").strip()
    language = str(language or "中文").strip().lower()
    locale = "en" if language in {"en", "english", "英文", "英语"} else "zh"
    profile = GENERIC_WORLD_MECHANICS
    for candidate in WORLD_MECHANIC_PROFILES:
        if any(keyword in theme for keyword in candidate["keywords"]):
            profile = candidate
            break
    mechanics = copy.deepcopy(profile[locale])
    mechanics["profile"] = profile["id"]
    return mechanics


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


def normalize_prompt_answer(key, raw):
    raw = str(raw or "").strip()
    if key == "difficulty":
        raw = {"1": "休闲", "2": "标准", "3": "硬核"}.get(raw, raw)
    elif key == "language":
        raw = {"1": "中文", "2": "English", "3": "日本語"}.get(raw, raw)
    return raw


def prompt_world():
    print("创建你的世界（只需回答4项；基地、危险、资源、天赋、探索方式和灾难周期由系统根据主题生成）：")
    answers = {}
    for key, label, example in REQUIRED_QUESTIONS:
        raw = normalize_prompt_answer(key, input(f"{label}（参考：{example}）："))
        if key == "theme" and raw in {"随机", "随机生成", "random", "Random"}:
            raw = random.choice(["永夜冰川", "巨兽背部", "废土列车", "深渊裂隙"])
        if key == "difficulty" and not raw:
            raw = "标准"
        if key == "narrative_length" and not raw:
            raw = "7"
        if key == "language" and not raw:
            raw = "中文"
        answers[key] = raw

    generated = generate_world_mechanics(answers["theme"], answers["language"])
    answers.update({
        "safe_base": generated["safe_base"],
        "external_dangers": generated["external_dangers"],
        "primary_resources": generated["primary_resources"],
        "exploration_method": generated["exploration_method"],
        "disaster_cycle": generated["disaster_cycle"],
        "disaster_type": generated["disaster_type"],
        "player_talent": generated["talent"],
    })
    world_name = re.sub(r'[<>:"/\\|?*]', "", answers["theme"]).replace("..", "").strip()
    answers["world_name"] = world_name[:32] or "新世界"
    print(
        "系统已根据主题生成："
        f"基地={generated['safe_base']}；危险={'、'.join(generated['external_dangers'])}；"
        f"资源={'、'.join(generated['primary_resources'])}；"
        f"探索={generated['exploration_method']}；灾难={generated['disaster_cycle']}。"
    )
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
    world["theme"] = str(world.get("theme") or "").strip()
    world["narrative_style"] = world.get("narrative_style") or "冷酷"
    world["difficulty"] = str(world.get("difficulty") or "").strip()
    world["language"] = str(world.get("language") or "中文").strip()

    generated = generate_world_mechanics(world["theme"], world["language"])

    try:
        world["narrative_length"] = int(world.get("narrative_length", 7))
    except (TypeError, ValueError) as exc:
        raise GeneratorError("narrative_length 必须是1到10的整数") from exc

    auto_generated_fields = []
    setting = world.setdefault("setting", {})
    setting["safe_base"] = str(setting.get("safe_base") or "").strip()
    if not setting["safe_base"]:
        setting["safe_base"] = generated["safe_base"]
        auto_generated_fields.append("setting.safe_base")
    setting["external_dangers"] = split_items(setting.get("external_dangers"))
    if not setting["external_dangers"]:
        setting["external_dangers"] = generated["external_dangers"]
        auto_generated_fields.append("setting.external_dangers")
    setting["exploration_method"] = str(setting.get("exploration_method") or "").strip()
    if not setting["exploration_method"]:
        setting["exploration_method"] = generated["exploration_method"]
        auto_generated_fields.append("setting.exploration_method")
    setting["disaster_cycle"] = str(setting.get("disaster_cycle") or "").strip()
    if not setting["disaster_cycle"]:
        setting["disaster_cycle"] = generated["disaster_cycle"]
        auto_generated_fields.append("setting.disaster_cycle")
    setting["disaster_type"] = str(setting.get("disaster_type") or generated["disaster_type"]).strip()

    resources = world.setdefault("resources", {})
    resources["primary"] = normalize_resource_items(resources.get("primary"))
    if not resources["primary"]:
        resources["primary"] = normalize_resource_items(generated["primary_resources"])
        auto_generated_fields.append("resources.primary")
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
    generated_talent = generated["talent"]
    talent_was_incomplete = not str(talent.get("name") or "").strip()
    talent["name"] = str(talent.get("name") or generated_talent["name"]).strip()
    for field in ("description", "type", "trigger", "effect", "limitations"):
        talent_was_incomplete = talent_was_incomplete or not str(talent.get(field) or "").strip()
        talent[field] = str(talent.get(field) or generated_talent[field]).strip()
    if talent_was_incomplete:
        auto_generated_fields.append("player_talent")

    supplied_bundle = world.get("generation_bundle")
    if isinstance(supplied_bundle, dict) and supplied_bundle.get("compiler_version"):
        bundle = copy.deepcopy(supplied_bundle)
    else:
        bundle = compile_world_bundle(
            theme=world["theme"],
            language=world["language"],
            mechanics=generated,
            safe_base=setting["safe_base"],
            primary_resources=[item["name"] for item in resources["primary"]],
        )
        auto_generated_fields.append("generation_bundle")
    world["generation_bundle"] = bundle
    for registry_name in ("locations", "targets", "combat_targets", "areas", "farm_areas", "build_catalog", "modules", "recipes", "disasters", "action_targets", "starting_inventory", "starting_npcs", "starting_factions", "starting_relationships"):
        if not world.get(registry_name) and bundle.get(registry_name) is not None:
            world[registry_name] = copy.deepcopy(bundle[registry_name])

    generation = world.setdefault("generation", {})
    generation["mechanics_source"] = "theme_profile"
    generation["theme_profile"] = generated["profile"]
    generation["generated_fields"] = auto_generated_fields

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
    bundle = world.get("generation_bundle", {}) if isinstance(world.get("generation_bundle", {}), dict) else {}
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
    starting_inventory = copy.deepcopy(bundle.get("starting_inventory", {}))
    inventory_resources = {item["name"]: 0 for item in primary_resources}
    inventory_resources.update(starting_inventory.get("resources", {}) if isinstance(starting_inventory.get("resources", {}), dict) else {})
    inventory_equipment = {"main_weapon": None, "off_hand": None, "helmet": None, "chest": None, "legs": None, "boots": None, "accessory_1": None, "accessory_2": None}
    inventory_equipment.update(starting_inventory.get("equipment", {}) if isinstance(starting_inventory.get("equipment", {}), dict) else {})
    files["inventory.yaml"] = {
        "inventory": {
            "equipment": inventory_equipment,
            "items": starting_inventory.get("items", []),
            "resources": inventory_resources,
            "weight_current": 0,
            "weight_max": 50,
            "currency": 0,
        }
    }
    files["npcs.yaml"] = {"npcs": copy.deepcopy(world.get("starting_npcs", bundle.get("starting_npcs", [])))}
    files["factions.yaml"] = {"factions": copy.deepcopy(world.get("starting_factions", bundle.get("starting_factions", [])))}
    files["relationships.yaml"] = {"relationships": copy.deepcopy(world.get("starting_relationships", bundle.get("starting_relationships", [])))}
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
            "current_location": bundle.get("starting_location", "camp_core"),
            "current_location_name": safe_base,
            "current_mode": "base",
            "in_combat": False,
            "available_time_minutes": 720,
            "day_elapsed_minutes": 0,
            "next_disaster_day": world["rules"]["disaster"]["cycle_days"],
            "narrative_state": {"pressure_components": {}, "open_loops": [], "payoff_history": [], "event_pattern_history": [], "recent_irreversible_changes": [], "current_arc": {}},
            "pressure_level": 30,
            "last_payoff_turn": 0,
            "active_mysteries": mysteries,
            "active_mystery_records": [{"id": mystery, "importance": 1, "waiting_turns": 0, "reminder_count": 0, "visibility": 1, "progress": 0} for mystery in mysteries],
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
        "data": {
            "world_name": world_name,
            "theme": world["theme"],
            "safe_base": safe_base,
            "difficulty": world["difficulty"],
            "generation_profile": world.get("generation", {}).get("theme_profile", "generic"),
            "registry_counts": {key: len(bundle.get(key, {})) if isinstance(bundle.get(key), (dict, list)) else 0 for key in ("locations", "enemies", "areas", "build_catalog", "action_targets")},
        },
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

        # 新存档从第一天起就初始化 SQLite 事实源；YAML/Markdown 只是可读投影。
        load_game_state(target).save()

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
