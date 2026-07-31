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
from engine_runtime.public_survival import initial_public_states
from engine_runtime.state import load_game_state


DIFFICULTIES = {"休闲", "标准", "硬核"}
DEATH_MODES = {"permanent", "checkpoint", "legacy"}


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


def normalize_public_survival(world, collective):
    """校验全民世界开局必须能让玩家一眼读懂的公开信息。"""
    raw = world.get("public_survival", {})
    if not collective:
        world["public_survival"] = raw if isinstance(raw, dict) else {}
        return
    if not isinstance(raw, dict):
        raise GeneratorError("全民求生世界必须提供 public_survival 对象")
    public = copy.deepcopy(raw)
    for field in ("system_name", "region_name", "opening_announcement"):
        public[field] = str(public.get(field) or "").strip()
    rules = public.get("opening_rules", [])
    if not isinstance(rules, list):
        rules = []
    public["opening_rules"] = [str(rule).strip() for rule in rules if str(rule).strip()]
    messages = public.get("starting_channel_messages", [])
    public["starting_channel_messages"] = [
        {"sender": str(item.get("sender") or "").strip(), "message": str(item.get("message") or "").strip()}
        for item in messages if isinstance(item, dict)
    ] if isinstance(messages, list) else []
    peers = public.get("initial_peers", [])
    normalized_peers = []
    for item in peers if isinstance(peers, list) else []:
        if not isinstance(item, dict):
            continue
        if not item.get("id") or not item.get("name"):
            raise GeneratorError("每个 initial_peer 必须有 id 和 name")
        if not item.get("opening_strategy") or not item.get("visible_edge"):
            raise GeneratorError(f"peer {item['id']} 必须提供 opening_strategy 和 visible_edge")
        normalized_peers.append(copy.deepcopy(item))
    public["initial_peers"] = normalized_peers
    if not all(public[field] for field in ("system_name", "region_name", "opening_announcement")):
        raise GeneratorError("全民求生世界必须给出系统名、区域名和开局公告")
    if not 4 <= len(public["opening_rules"]) <= 6:
        raise GeneratorError("全民求生开局必须有4到6条直白规则")
    if not 3 <= len(public["starting_channel_messages"]) <= 5 or any(not item["sender"] or not item["message"] for item in public["starting_channel_messages"]):
        raise GeneratorError("全民求生开局必须有3到5条带发送者的区域频道消息")
    if not 3 <= len(public["initial_peers"]) <= 5 or any(not all(peer.values()) for peer in public["initial_peers"]):
        raise GeneratorError("全民求生开局必须有3到5名可见对手，并说明其策略和优势")
    if len({peer["id"] for peer in public["initial_peers"]}) != len(public["initial_peers"]):
        raise GeneratorError("全民求生开局对手 id 不能重复")
    competition = public.get("competition", {})
    if not isinstance(competition, dict):
        raise GeneratorError("全民求生世界必须提供 competition 对象")
    competition = copy.deepcopy(competition)
    numeric_fields = (
        "initial_percentile", "location_discovery_bonus", "knowledge_bonus",
        "positive_resource_bonus_cap", "percentile_per_score", "loss_roll_threshold",
        "losses_per_trigger", "rank_season_end_turn", "active_rival_count",
    )
    for field in numeric_fields:
        value = competition.get(field)
        if isinstance(value, bool):
            raise GeneratorError(f"public_survival.competition.{field} 必须是数值")
        try:
            competition[field] = float(value)
        except (TypeError, ValueError) as exc:
            raise GeneratorError(f"public_survival.competition.{field} 必须是数值") from exc
    if not 1 <= competition["initial_percentile"] <= 99:
        raise GeneratorError("public_survival.competition.initial_percentile 必须在1到99之间")
    if not 0 <= competition["loss_roll_threshold"] <= 100:
        raise GeneratorError("public_survival.competition.loss_roll_threshold 必须在0到100之间")
    for field in ("location_discovery_bonus", "knowledge_bonus", "positive_resource_bonus_cap", "percentile_per_score", "losses_per_trigger"):
        if competition[field] < 0:
            raise GeneratorError(f"public_survival.competition.{field} 不能为负数")
    if competition["rank_season_end_turn"] < 1:
        raise GeneratorError("public_survival.competition.rank_season_end_turn 必须至少为1")
    for field in ("losses_per_trigger", "rank_season_end_turn", "active_rival_count"):
        if not competition[field].is_integer():
            raise GeneratorError(f"public_survival.competition.{field} 必须是整数")
    if not 1 <= competition["active_rival_count"] <= len(public["initial_peers"]):
        raise GeneratorError("public_survival.competition.active_rival_count 必须介于1和可见竞争者数量之间")
    raw_scores = competition.get("outcome_scores")
    required_outcomes = ("大成功", "普通成功", "成功但付出代价", "失败但获得部分信息", "局部失败", "严重失败", "死亡")
    if not isinstance(raw_scores, dict) or any(outcome not in raw_scores for outcome in required_outcomes):
        raise GeneratorError("public_survival.competition.outcome_scores 必须定义全部正式行动结果")
    scores = {}
    for outcome in required_outcomes:
        value = raw_scores[outcome]
        if isinstance(value, bool):
            raise GeneratorError(f"public_survival.competition.outcome_scores.{outcome} 必须是数值")
        try:
            scores[outcome] = float(value)
        except (TypeError, ValueError) as exc:
            raise GeneratorError(f"public_survival.competition.outcome_scores.{outcome} 必须是数值") from exc
    competition["outcome_scores"] = scores
    for field in ("losses_per_trigger", "rank_season_end_turn", "active_rival_count"):
        competition[field] = int(competition[field])
    public["competition"] = competition
    world["public_survival"] = public


def initial_talent_effects(talent):
    """直接采用本世界 LLM 声明的可执行天赋合同，不套用固定类别效果。"""
    effect = talent.get("mechanical_effect", {}) if isinstance(talent, dict) else {}
    modifiers = effect.get("action_modifiers", {}) if isinstance(effect, dict) else {}
    return {"action_modifiers": copy.deepcopy(modifiers) if isinstance(modifiers, dict) else {}}


def normalize_talent_effect(raw, label):
    if not isinstance(raw, dict):
        raise GeneratorError(f"{label} 必须是对象")
    effect = copy.deepcopy(raw)
    modifiers = effect.get("action_modifiers", {})
    bonuses = effect.get("attribute_bonus", {})
    if not isinstance(modifiers, dict) or not isinstance(bonuses, dict):
        raise GeneratorError(f"{label}.action_modifiers 和 {label}.attribute_bonus 必须是对象")
    if not modifiers and not bonuses:
        raise GeneratorError(f"{label} 必须至少定义一项可执行效果")
    effect["action_modifiers"] = modifiers
    if bonuses:
        effect["attribute_bonus"] = bonuses
    return effect


def normalize_talent_deck(world):
    """升级三选一卡池必须来自当前世界包，不能退回全局固定三张卡。"""
    raw_deck = world.get("talent_deck", [])
    if not isinstance(raw_deck, list) or len(raw_deck) < 3:
        raise GeneratorError("LLM 世界包必须提供至少3张原创升级天赋卡")
    deck = []
    ids = set()
    for index, raw_card in enumerate(raw_deck):
        if not isinstance(raw_card, dict):
            raise GeneratorError(f"talent_deck[{index}] 必须是对象")
        card = copy.deepcopy(raw_card)
        for field in ("id", "name", "description"):
            card[field] = str(card.get(field) or "").strip()
            if not card[field]:
                raise GeneratorError(f"talent_deck[{index}].{field} 不能为空")
        if card["id"] in ids:
            raise GeneratorError("talent_deck 的 id 不能重复")
        ids.add(card["id"])
        card["rarity"] = normalize_rating(card.get("rarity"), default="B")
        card["effect"] = normalize_talent_effect(card.get("effect"), f"talent_deck[{index}].effect")
        deck.append(card)
    world["talent_deck"] = deck


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
    
    # P0-1: 修复 rules:null 与 setdefault() 不兼容的问题
    rules = world.setdefault("rules", {})
    
    if not isinstance(rules.get("disaster"), dict):
        rules["disaster"] = {}
    
    if not isinstance(rules.get("death"), dict):
        rules["death"] = {}
    
    disaster_rules = rules["disaster"]
    death_rules = rules["death"]
    
    disaster_rules["cycle_days"] = cycle_days
    disaster_rules["first_event"] = str(disaster_rules.get("first_event") or f"第{cycle_days}天")
    death_rules["type"] = death_rules.get("type") or infer_death_mode(world["difficulty"])
    if death_rules["type"] not in DEATH_MODES:
        raise GeneratorError("rules.death.type 必须是 permanent/checkpoint/legacy")

    talent = talent or {}
    for field in ("name", "description", "trigger", "effect", "limitations"):
        talent[field] = str(talent.get(field) or "").strip()
    talent["mechanical_effect"] = normalize_talent_effect(talent.get("mechanical_effect"), "player_talent.mechanical_effect")
    strategic_loop = talent.get("strategic_loop", {})
    strategic_loop = strategic_loop if isinstance(strategic_loop, dict) else {}
    for field in ("input", "conversion", "competitive_impact", "counterplay"):
        strategic_loop[field] = str(strategic_loop.get(field) or "").strip()
    talent["strategic_loop"] = strategic_loop
    opening_card = talent.get("opening_card", {})
    opening_card = opening_card if isinstance(opening_card, dict) else {}
    for field in ("advantage", "first_use", "comparison", "hard_limit"):
        opening_card[field] = str(opening_card.get(field) or "").strip()
    talent["opening_card"] = opening_card
    talent["rarity"] = normalize_rating(talent.get("rarity"), default="A")
    if any(not talent[field] for field in ("name", "description", "trigger", "effect", "limitations")):
        raise GeneratorError("LLM 世界包必须完整定义主角天赋的 name/description/trigger/effect/limitations")
    if any(not strategic_loop[field] for field in ("input", "conversion", "competitive_impact", "counterplay")):
        raise GeneratorError("主角天赋必须定义独占循环的 input/conversion/competitive_impact/counterplay")
    if any(not opening_card[field] for field in ("advantage", "first_use", "comparison", "hard_limit")):
        raise GeneratorError("LLM 世界包必须完整定义主角天赋 opening_card 的 advantage/first_use/comparison/hard_limit")

    profession_source = world.get("professions", {})
    genre_contract_choice = world.get("genre_contract", "1")
    selected_genre_contract = (
        copy.deepcopy(genre_contract_choice)
        if isinstance(genre_contract_choice, dict)
        else parse_genre_contract_choice(genre_contract_choice, world["theme"])
    )
    world["genre_contract"] = selected_genre_contract
    normalize_public_survival(world, bool(selected_genre_contract.get("collective_transmission")))
    normalize_talent_deck(world)
    supplied_bundle = world.get("generation_bundle")
    if isinstance(supplied_bundle, dict) and supplied_bundle.get("compiler_version") == COMPILER_VERSION:
        bundle = copy.deepcopy(supplied_bundle)
        mechanics_source = "llm_compiled_bundle"
    else:
        # P0-2/P0-3/P0-4: 从统一的 world.mechanics 路径读取 capabilities 和 ranking
        mechanics_cfg = world.get("mechanics", {})
        
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
                    # P0-2/P0-3/P0-4: 传递统一的 mechanics 配置
                    "capabilities": mechanics_cfg.get("capabilities", {}),
                    "ranking": mechanics_cfg.get("ranking", {}),
                    "peer_simulation": mechanics_cfg.get("peer_simulation", {}),
                },
                safe_base=setting["safe_base"],
                primary_resources=[item["name"] for item in resources["primary"]],
                genre_contract=selected_genre_contract,
            )
        except ValueError as exc:
            raise GeneratorError(f"LLM 世界蓝图不完整或不可编译：{exc}") from exc
        mechanics_source = "llm_world_blueprint"
    world["generation_bundle"] = bundle
    for registry_name in ("locations", "targets", "combat_targets", "enemy_definitions", "encounter_entities", "areas", "farm_areas", "build_catalog", "modules", "recipes", "disasters", "action_targets", "professions", "starting_inventory", "starting_npcs", "starting_factions", "starting_relationships", "event_pool", "creative_slots"):
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
    phases = world.get("phases")
    if not isinstance(phases, list) or not phases or not isinstance(phases[0], dict) or not str(phases[0].get("name") or "").strip():
        raise GeneratorError("LLM 世界包必须提供首个阶段名称 world.phases[0].name")
    phase = str(phases[0]["name"]).strip()
    bundle = world.get("generation_bundle", {}) if isinstance(world.get("generation_bundle", {}), dict) else {}
    mysteries = [
        item.get("question", str(item)) if isinstance(item, dict) else str(item)
        for item in world.get("mysteries", [])[:5]
    ]
    primary_resources = world["resources"]["primary"]
    public_states = initial_public_states(world)
    initial_attributes = {"strength": 5, "constitution": 5, "agility": 5, "spirit": 5}
    initial_bonus = talent.get("mechanical_effect", {}).get("attribute_bonus", {})
    if isinstance(initial_bonus, dict):
        for attribute, delta in initial_bonus.items():
            if attribute in initial_attributes:
                try:
                    initial_attributes[attribute] += float(delta)
                except (TypeError, ValueError):
                    pass

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
            "attributes": initial_attributes,
            "free_points": 4,
            "hp": 50,
            "max_hp": 50,
            "status_effects": [],
            "hunger": 100,
            "fatigue": 0,
            "mental": 100,
            "max_mental": 100,
            "talents": [{**talent, "obtained_turn": 1}],
            "talent_effects": initial_talent_effects(talent),
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
            "world_turn": 1,  # P0-5: 初始化 world_turn 与 current_turn 同步
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
            "current_location": bundle["starting_location"],
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
            "genre_contract_id": world.get("genre_contract", {}).get("id"),
            "public_system_enabled": bool(public_states.get("public_system_state", {}).get("enabled")),
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
        *( [f"区域“{world['public_survival']['region_name']}”已开启公开频道与排行榜，所有人从同一规则起跑。"] if public_states.get("public_system_state", {}).get("enabled") else [] ),
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
    files["population_state.yaml"] = {"population_state": public_states["population_state"] or {
        "populated_npcs": {}, "npc_faction_memberships": {}, "npc_location_history": {},
        "population_cap_used": 0, "population_cap_total": 10, "settlement_count": 0,
    }}
    files["public_system_state.yaml"] = {"public_system_state": public_states["public_system_state"] or {
        "global_events_active": [], "system_announcements": [], "active_rules_modifiers": [],
        "public_quest_line": [], "achievements_unlocked": [], "system_level_progression": {},
    }}
    files["market_state.yaml"] = {"market_state": public_states["market_state"] or {
        "market_enabled": False, "available_vendors": [], "market_prices": {},
        "player_inventory_listings": [], "recent_transactions": [], "market_trends": {},
    }}
    files["ranking_state.yaml"] = {"ranking_state": public_states["ranking_state"] or {
        "player_rank_global": None, "player_rank_regional": None, "leaderboards": {},
        "rank_season_current": 1, "rank_season_end_turn": 100, "prestige_points": 0,
    }}
    files["comparative_state.yaml"] = {"comparative_state": public_states["comparative_state"] or {
        "player_comparison_baseline": {}, "performance_metrics_history": [],
        "best_performance_by_category": {}, "comparison_partners": [], "comparison_last_updated": None,
    }}
    files["rival_state.yaml"] = {"rival_state": public_states["rival_state"] or {
        "active_rivals": [], "rival_relationships": {}, "rival_competitions_active": [],
        "rival_score_current": 0, "rival_score_target": 0, "rivalry_win_rate": 0.0,
        "last_rival_encounter": None,
    }}
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
        game_state = load_game_state(target)
        game_state.save()

        # Generate and persist peer agents for public survival worlds
        if world.get("genre_contract", {}).get("collective_transmission"):
            from engine_runtime.world_compiler import _generate_peer_agents_from_public_survival
            from engine_runtime.persistence import insert_peer_agent
            import random

            peers = _generate_peer_agents_from_public_survival(
                world,
                world.get("generation_bundle", {}),
            )
            
            # Enhance peers with diverse personality profiles
            for peer in peers:
                # Generate diverse personality profile (not all 50s!)
                peer.personality_traits = {
                    "caution": round(random.uniform(20, 80), 1),
                    "ambition": round(random.uniform(20, 80), 1),
                    "empathy": round(random.uniform(20, 80), 1),
                    "honesty": round(random.uniform(20, 80), 1),
                    "openness": round(random.uniform(20, 80), 1),
                    "collectivism": round(random.uniform(20, 80), 1),
                }
                
                # Assign goal based on traits
                ambition_level = peer.personality_traits.get("ambition", 50)
                if ambition_level > 70:
                    peer.primary_goal = "maximize_resources"
                elif ambition_level < 30:
                    peer.primary_goal = "survival"
                else:
                    peer.primary_goal = "balanced_growth"
                
                # Give some starting inventory
                peer.inventory_resources = {
                    "scrap": random.randint(10, 50),
                    "fuel": random.randint(5, 20),
                    "food": random.randint(10, 30),
                }
                
                # Occasionally give equipment
                if random.random() < 0.3:  # 30% chance
                    equipment_types = ["basic_weapon", "toolkit", "medical_kit", "defense_gear"]
                    peer.equipment["main_weapon"] = random.choice(equipment_types)
            
            for peer in peers:
                insert_peer_agent(game_state, world["name"], peer)
            print(f"已生成 {len(peers)} 个 PeerAgent 实体（包含多样人格和资源）")

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
