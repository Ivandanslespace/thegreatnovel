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

from engine_runtime.world_compiler import COMPILER_VERSION, compile_world_bundle
from engine_runtime.ratings import normalize_rating
from engine_runtime.state import load_game_state


DIFFICULTIES = {"休闲", "标准", "硬核"}
DEATH_MODES = {"permanent", "checkpoint", "legacy"}


def get_default_genre_contract(theme: str) -> dict:
    """根据主题返回默认的类型合同。
    
    废土列车、永夜冰川、巨兽背部、深渊裂隙等主题默认使用全民系统投放型求生。
    """
    # 所有主要主题都默认使用 mass_system_survival
    mass_survival_themes = {"废土列车", "永夜冰川", "巨兽背部", "深渊裂隙"}
    
    if theme in mass_survival_themes:
        return {
            "id": "mass_system_survival",
            "name": "全民系统投放型求生",
            "collective_transmission": True,
            "shared_start": True,
            "region_size": 1000,
            "global_count": 100000000,
            "public_system": {
                "regional_chat": True,
                "private_chat": True,
                "trading": True,
                "rankings": True,
                "achievements": True,
                "announcements": True,
            },
            "protagonist_contract": {
                "unique_mechanic_required": True,
                "comparative_advantage_target": 0.60,
                "automatic_success": False,
                "tone": ["rational", "confident", "proactive"],
            },
            "population_distribution": {
                "panicked_players": {"min": 0.15, "max": 0.20},
                "ordinary_players": {"min": 0.45, "max": 0.55},
                "skilled_players": {"min": 0.20, "max": 0.25},
                "regional_elites": {"min": 0.05, "max": 0.08},
                "special_rivals": {"min": 0.01, "max": 0.03},
            },
            "difficulty_calibration": {
                "system_operations": {"resistance_min": 0, "resistance_max": 6},
                "daily_talk": {"resistance_min": 4, "resistance_max": 8},
                "newbie_exploration": {"resistance_min": 10, "resistance_max": 16},
                "normal_danger": {"resistance_min": 18, "resistance_max": 24},
                "high_risk": {"resistance_min": 28, "resistance_max": 38},
            },
            "failure_distribution": {
                "critical_success_pct": {"min": 0.08, "max": 0.10},
                "normal_success_pct": {"min": 0.70, "max": 0.75},
                "costly_success_pct": {"min": 0.15, "max": 0.22},
                "partial_failure_pct": {"min": 0.55, "max": 0.65},
                "severe_failure_pct": {"min": 0.30, "max": 0.40},
                "catastrophic_failure_pct": 0.05,
            },
        }
    else:
        # 其他主题默认使用 solo_survival
        return {
            "id": "solo_survival",
            "name": "孤独生存",
            "collective_transmission": False,
            "shared_start": False,
            "region_size": None,
            "global_count": None,
            "public_system": {},
            "protagonist_contract": {
                "unique_mechanic_required": False,
                "comparative_advantage_target": None,
                "automatic_success": False,
                "tone": ["isolated", "cautious"],
            },
        }
REQUIRED_QUESTIONS = (
    ("theme", "世界主题", "永夜冰川 / 巨兽背部 / 废土列车 / 深渊裂隙；也可自定义"),
    ("genre_contract", "世界类型", "1=全民系统投放型求生（推荐），2=全民求生：百倍奖励，3=孤独生存"),
    ("difficulty", "游戏残酷程度", "1=休闲，2=标准，3=硬核永久死亡"),
    ("narrative_length", "每段叙述长度（1-10）", "1=极短，5=中等，7=标准，10=极长"),
    ("language", "游戏语言", "1=中文，2=English，3=日本語；留空为中文"),
)


def parse_genre_contract_choice(choice: str, theme: str) -> dict:
    """解析玩家选择的类型合同。
    
    Args:
        choice: 玩家输入（"1", "2", "3" 或具体类型名称）
        theme: 世界主题
    
    Returns:
        对应的类型合同字典
    """
    # 标准化输入
    choice = str(choice).strip().lower()
    
    # 选项 1: 全民系统投放型求生（推荐）
    if choice in ["1", "mass_system_survival", "全民系统投放", "全民"]:
        return {
            "id": "mass_system_survival",
            "name": "全民系统投放型求生",
            "collective_transmission": True,
            "shared_start": True,
            "region_size": 1000,
            "global_count": 100000000,
            "public_system": {
                "regional_chat": True,
                "private_chat": True,
                "trading": True,
                "rankings": True,
                "achievements": True,
                "announcements": True,
            },
            "protagonist_contract": {
                "unique_mechanic_required": True,
                "comparative_advantage_target": 0.60,
                "automatic_success": False,
                "tone": ["rational", "confident", "proactive"],
            },
            "population_distribution": {
                "panicked_players": {"min": 0.15, "max": 0.20},
                "ordinary_players": {"min": 0.45, "max": 0.55},
                "skilled_players": {"min": 0.20, "max": 0.25},
                "regional_elites": {"min": 0.05, "max": 0.08},
                "special_rivals": {"min": 0.01, "max": 0.03},
            },
            "difficulty_calibration": {
                "system_operations": {"resistance_min": 0, "resistance_max": 6},
                "daily_talk": {"resistance_min": 4, "resistance_max": 8},
                "newbie_exploration": {"resistance_min": 10, "resistance_max": 16},
                "normal_danger": {"resistance_min": 18, "resistance_max": 24},
                "high_risk": {"resistance_min": 28, "resistance_max": 38},
            },
            "failure_distribution": {
                "critical_success_pct": {"min": 0.08, "max": 0.10},
                "normal_success_pct": {"min": 0.70, "max": 0.75},
                "costly_success_pct": {"min": 0.15, "max": 0.22},
                "partial_failure_pct": {"min": 0.55, "max": 0.65},
                "severe_failure_pct": {"min": 0.30, "max": 0.40},
                "catastrophic_failure_pct": 0.05,
            },
        }
    
    # 选项 2: 全民求生：百倍奖励
    elif choice in ["2", "mass_reward_survival", "百倍奖励", "全民奖励"]:
        return {
            "id": "mass_reward_survival",
            "name": "全民求生：百倍奖励",
            "collective_transmission": True,
            "shared_start": True,
            "region_size": 1000,
            "global_count": 100000000,
            "public_system": {
                "regional_chat": True,
                "private_chat": True,
                "trading": True,
                "rankings": True,
                "achievements": True,
                "announcements": True,
            },
            "protagonist_contract": {
                "unique_mechanic_required": True,
                "comparative_advantage_target": 0.70,
                "automatic_success": False,
                "reward_multiplier": 100,
                "concealment_required": True,
                "tone": ["cautious", "strategic", "low_profile"],
            },
            "population_distribution": {
                "panicked_players": {"min": 0.15, "max": 0.20},
                "ordinary_players": {"min": 0.45, "max": 0.55},
                "skilled_players": {"min": 0.20, "max": 0.25},
                "regional_elites": {"min": 0.05, "max": 0.08},
                "special_rivals": {"min": 0.01, "max": 0.03},
            },
            "difficulty_calibration": {
                "system_operations": {"resistance_min": 0, "resistance_max": 6},
                "daily_talk": {"resistance_min": 4, "resistance_max": 8},
                "newbie_exploration": {"resistance_min": 10, "resistance_max": 16},
                "normal_danger": {"resistance_min": 18, "resistance_max": 24},
                "high_risk": {"resistance_min": 28, "resistance_max": 38},
            },
            "failure_distribution": {
                "critical_success_pct": {"min": 0.08, "max": 0.10},
                "normal_success_pct": {"min": 0.70, "max": 0.75},
                "costly_success_pct": {"min": 0.15, "max": 0.22},
                "partial_failure_pct": {"min": 0.55, "max": 0.65},
                "severe_failure_pct": {"min": 0.30, "max": 0.40},
                "catastrophic_failure_pct": 0.05,
            },
        }
    
    # 选项 3: 孤独生存
    elif choice in ["3", "solo_survival", "孤独", "单人"]:
        return {
            "id": "solo_survival",
            "name": "孤独生存",
            "collective_transmission": False,
            "shared_start": False,
            "region_size": None,
            "global_count": None,
            "public_system": {},
            "protagonist_contract": {
                "unique_mechanic_required": False,
                "comparative_advantage_target": None,
                "automatic_success": False,
                "tone": ["isolated", "cautious"],
            },
        }
    
    # 默认：全民系统投放型求生
    else:
        return parse_genre_contract_choice("1", theme)


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
                "name": "系统共鸣·解析",
                "description": "你的系统面板与其他求生者不同，能够解析隐藏的物品属性、NPC 真实意图和区域规则的漏洞。",
                "type": "信息类",
                "trigger": "观察物品、NPC 对话或探索异常现象时",
                "effect": "有概率看到其他人看不到的隐藏信息（物品真实价值、NPC 谎言标记、规则漏洞提示），并获得一次性'解析点数'用于主动查询",
                "limitations": "每日解析次数有限（初始 3 次/天），且对高等级存在或强加密信息的解析可能失败；过度使用会引来'系统监察者'的注意",
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
                "name": "System Resonance: Analysis",
                "description": "Your system panel differs from other survivors—you can analyze hidden item properties, NPC true intentions, and loopholes in regional rules.",
                "type": "Information",
                "trigger": "When observing items, NPC dialogue, or exploring anomalous phenomena",
                "effect": "Chance to see hidden information others cannot (true item value, NPC lie markers, rule loophole hints); gain one-time 'Analysis Points' for active queries",
                "limitations": "Limited daily analyses (starts at 3/day); may fail against high-level entities or strongly encrypted info; overuse attracts 'System Overseer' attention",
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
    raise GeneratorError(
        "交互式 CLI 只知道玩家偏好，不能替代 LLM 的世界创作。"
        "请由主持 LLM 按 templates/world_template.yaml 创作完整 world_blueprint，"
        "保存为 YAML 后使用 --answers 创建存档。"
    )


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
    """固化 LLM 创作包，而不从主题关键词回填任何世界内容。"""
    world = deep_merge(template["world"], supplied_world)
    talent = deep_merge(template.get("player_talent", {}), supplied_talent)

    if world_name_override:
        world["name"] = world_name_override
    world["name"] = safe_world_name(world.get("name"))
    world["theme"] = str(world.get("theme") or "").strip()
    world["narrative_style"] = str(world.get("narrative_style") or "").strip()
    world["difficulty"] = str(world.get("difficulty") or "").strip()
    world["language"] = str(world.get("language") or "中文").strip()
    try:
        world["narrative_length"] = int(world.get("narrative_length", 7))
    except (TypeError, ValueError) as exc:
        raise GeneratorError("narrative_length 必须是1到10的整数") from exc

    setting = world.setdefault("setting", {})
    setting["safe_base"] = str(setting.get("safe_base") or "").strip()
    setting["external_dangers"] = split_items(setting.get("external_dangers"))
    setting["exploration_method"] = str(setting.get("exploration_method") or "").strip()
    setting["disaster_cycle"] = str(setting.get("disaster_cycle") or "").strip()
    setting["disaster_type"] = str(setting.get("disaster_type") or "").strip()

    resources = world.setdefault("resources", {})
    resources["primary"] = normalize_resource_items(resources.get("primary"))
    resources["secondary"] = normalize_resource_items(resources.get("secondary"))
    resources["rare"] = normalize_resource_items(resources.get("rare"))
    resources["currency"] = str(resources.get("currency") or "").strip()

    if not world["theme"]:
        raise GeneratorError("世界主题不能为空")
    if not setting["safe_base"]:
        raise GeneratorError("LLM 世界包必须定义安全基地")
    if not setting["external_dangers"]:
        raise GeneratorError("LLM 世界包必须定义至少一项外部主要危险")
    if not setting["exploration_method"]:
        raise GeneratorError("LLM 世界包必须定义探索方式")
    if not setting["disaster_cycle"] or not setting["disaster_type"]:
        raise GeneratorError("LLM 世界包必须定义灾难类型与周期")
    if world["difficulty"] not in DIFFICULTIES:
        raise GeneratorError("difficulty 必须是：休闲、标准或硬核")
    if not 1 <= world["narrative_length"] <= 10:
        raise GeneratorError("narrative_length 必须在1到10之间")
    if not 3 <= len(resources["primary"]) <= 5:
        raise GeneratorError("基础资源必须是3到5种")

    cycle_days = first_number(setting["disaster_cycle"])
    if cycle_days is None or cycle_days < 1:
        raise GeneratorError("灾难周期必须包含一个正整数天数")
    disaster_rules = world.setdefault("rules", {}).setdefault("disaster", {})
    disaster_rules["cycle_days"] = cycle_days
    disaster_rules["first_event"] = str(disaster_rules.get("first_event") or f"第{cycle_days}天")
    death_rules = world["rules"].setdefault("death", {})
    death_rules["type"] = death_rules.get("type") or infer_death_mode(world["difficulty"])
    if death_rules["type"] not in DEATH_MODES:
        raise GeneratorError("rules.death.type 必须是 permanent/checkpoint/legacy")

    talent = talent or {}
    for field in ("name", "description", "type", "trigger", "effect", "limitations"):
        talent[field] = str(talent.get(field) or "").strip()
    talent["rarity"] = normalize_rating(talent.get("rarity"), default="A")
    if any(not talent[field] for field in ("name", "description", "type", "trigger", "effect", "limitations")):
        raise GeneratorError("LLM 世界包必须完整定义主角天赋的 name/description/type/trigger/effect/limitations")

    profession_source = world.get("professions", {})
    genre_contract_choice = world.get("genre_contract", "1")
    selected_genre_contract = (
        copy.deepcopy(genre_contract_choice)
        if isinstance(genre_contract_choice, dict)
        else parse_genre_contract_choice(genre_contract_choice, world["theme"])
    )
    supplied_bundle = world.get("generation_bundle")
    if isinstance(supplied_bundle, dict) and supplied_bundle.get("compiler_version") == COMPILER_VERSION:
        bundle = copy.deepcopy(supplied_bundle)
        mechanics_source = "llm_compiled_bundle"
    else:
        try:
            bundle = compile_world_bundle(
                theme=world["theme"],
                language=world["language"],
                mechanics={
                    "world_blueprint": world.get("world_blueprint"),
                    "professions": profession_source,
                    "disaster_type": setting["disaster_type"],
                    "disaster_cycle_days": cycle_days,
                    "creative_slots": world.get("creative_slots", {}),
                    "motifs": world.get("motifs", []),
                    "taboo_domains": world.get("taboo_domains", []),
                },
                safe_base=setting["safe_base"],
                primary_resources=[item["name"] for item in resources["primary"]],
                genre_contract=selected_genre_contract,
            )
        except ValueError as exc:
            raise GeneratorError(f"LLM 世界蓝图不完整或不可编译：{exc}") from exc
        mechanics_source = "llm_world_blueprint"
    world["generation_bundle"] = bundle
    for registry_name in ("locations", "targets", "combat_targets", "enemy_definitions", "encounter_entities", "areas", "farm_areas", "build_catalog", "modules", "recipes", "disasters", "action_targets", "professions", "starting_inventory", "starting_npcs", "starting_factions", "starting_relationships"):
        if not world.get(registry_name) and bundle.get(registry_name) is not None:
            world[registry_name] = copy.deepcopy(bundle[registry_name])
    for content_name in ("motifs", "taboo_domains"):
        if not world.get(content_name) and bundle.get(content_name) is not None:
            world[content_name] = copy.deepcopy(bundle[content_name])

    generation = world.setdefault("generation", {})
    generation["mechanics_source"] = mechanics_source
    generation["world_creator"] = "llm"
    generation["generated_fields"] = []

    starting_profession = world.get("starting_profession")
    if starting_profession and str(starting_profession) not in world.get("professions", {}):
        raise GeneratorError("starting_profession 必须是本世界 professions 中由 LLM 定义的职业")
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
            "talents": [{**talent, "obtained_turn": 1}],
            "profession": world.get("starting_profession"),
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
    starting_npcs_list = copy.deepcopy(world.get("starting_npcs", bundle.get("starting_npcs", [])))
    files["npcs.yaml"] = {"npcs": starting_npcs_list}
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
            "active_encounters": [],
            "current_encounter_id": None,
            "encounter_history": [],
            "pending_options": {},
            "pending_options_state_turn": 1,
            "pending_reaction": {},
            "campaign_status": "active",
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
            "generation_source": world.get("generation", {}).get("mechanics_source", "llm_world_blueprint"),
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
    
    # 新增状态文件（向后兼容：旧存档缺少这些文件时视为空状态）
    files["region_state.yaml"] = {
        "region_state": {
            "discovered_locations": [],
            "explored_areas": {},
            "location_discovery_progress": {},
            "last_known_region": None,
            "regional_reputation": {}
        }
    }
    files["population_state.yaml"] = {
        "population_state": {
            "populated_npcs": {},
            "npc_faction_memberships": {},
            "npc_location_history": {},
            "population_cap_used": 0,
            "population_cap_total": 10,
            "settlement_count": 0
        }
    }
    files["public_system_state.yaml"] = {
        "public_system_state": {
            "global_events_active": [],
            "system_announcements": [],
            "active_rules_modifiers": [],
            "public_quest_line": [],
            "achievements_unlocked": [],
            "system_level_progression": {}
        }
    }
    files["market_state.yaml"] = {
        "market_state": {
            "market_enabled": False,
            "available_vendors": [],
            "market_prices": {},
            "player_inventory_listings": [],
            "recent_transactions": [],
            "market_trends": {}
        }
    }
    files["ranking_state.yaml"] = {
        "ranking_state": {
            "player_rank_global": None,
            "player_rank_regional": None,
            "leaderboards": {},
            "rank_season_current": 1,
            "rank_season_end_turn": 100,
            "prestige_points": 0
        }
    }
    files["comparative_state.yaml"] = {
        "comparative_state": {
            "player_comparison_baseline": {},
            "performance_metrics_history": [],
            "best_performance_by_category": {},
            "comparison_partners": [],
            "comparison_last_updated": None
        }
    }
    files["rival_state.yaml"] = {
        "rival_state": {
            "active_rivals": [],
            "rival_relationships": {},
            "rival_competitions_active": [],
            "rival_score_current": 0,
            "rival_score_target": 0,
            "rivalry_win_rate": 0.0,
            "last_rival_encounter": None
        }
    }
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
