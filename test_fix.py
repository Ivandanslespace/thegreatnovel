#!/usr/bin/env python3
"""Test fix for P0-4 genre assumptions."""

import sys
import yaml
from tools.create_save import normalize_package, GeneratorError

# Test 1: Ship no disaster world (without disaster_cycle and disaster_type)
ship_world = {
    "name": "星舰家园",
    "theme": "星际旅行",
    "difficulty": "休闲",
    "narrative_length": 7,
    "language": "中文",
    "genre_contract": "4",
    "setting": {
        "vehicle_base": "星舰普罗米修斯号",
        "navigation_tools": "量子导航仪",
        "exploration_method": "轨道扫描与登陆探索",
    },
    "resources": {
        "primary": ["能源", "水", "氧气", "食物合成剂", "零件"],
    },
    "rules": {
        "death": {"type": "checkpoint"},
    },
    "talent": {
        "name": "领航员天赋",
        "description": "擅长星际导航与资源分配",
        "trigger": "当星舰进行超空间跳跃时",
        "effect": "提高跳跃成功率，减少航行时间",
        "limitations": "无法在未知星系使用",
        "mechanical_effect": "bonus_navigation",
        "strategic_loop": {
            "input": "导航数据",
            "conversion": "跳跃路径优化",
            "competitive_impact": "更快到达目标星系",
            "counterplay": "敌对势力劫持导航系统",
        },
        "opening_card": {
            "advantage": "初始拥有完整星图",
            "first_use": "第一站选择安全航线",
            "comparison": "比其他玩家节省 30% 航行时间",
            "hard_limit": "只能在已知星系间跳跃",
        },
        "rarity": "A",
    },
    "world_blueprint": {
        "locations": [
            {"id": "bridge", "name": "指挥中心", "safe": True, "discovered": True},
            {"id": "habitat_ring", "name": "居住环", "safe": True, "discovered": True},
            {"id": "engineering_deck", "name": "引擎舱", "safe": True, "discovered": True},
            {"id": "cargo_bay", "name": "货舱", "safe": False, "discovered": True},
        ],
        "starting_location": "bridge",
        "enemies": [],
        "areas": [],
        "modules": [{"id": "hyperdrive_engine", "name": "超光速引擎"}],
        "recipes": [{"id": "synthesize_food", "name": "食物合成", "materials": {"能源": 50, "营养粉": 10}}],
        "action_targets": [{"id": "navigate"}],
        "npcs": [
            {"id": "captain", "name": "舰长", "status": "active", "location": "bridge", "goal": "寻找新家园"},
        ],
        "factions": [],
        "relationships": [],
        "starting_inventory": {
            "resources": {"能源": 100, "水": 50, "氧气": 50},
            "equipment": [{"id": "navigation_device", "durability": 10}],
            "items": [{"id": "star_chart", "quantity": 1}],
        },
        "event_pool": [
            {"id": "evt_001", "type": "NAVIGATION_CHALLENGE"},
            {"id": "evt_002", "type": "RESOURCE_MANAGEMENT"},
            {"id": "evt_003", "type": "NPC_INTERACTION"},
        ],
        "creative_slots": {},
        "motifs": ["希望", "探索", "文明延续"],
        "taboo_domains": ["反人类行为"],
    }
}

try:
    print("测试 1: 无灾难星舰世界...")
    world, talent = normalize_package({"world": {}, "player_talent": {}}, ship_world)
    print(f"✓ 世界创建成功：{world['name']}")
    print(f"  Genre: {world.get('genre_contract', {}).get('id')}")
    print(f"  载具基地：{world['setting'].get('vehicle_base')}")
    print(f"  灾难周期：{world['setting'].get('disaster_cycle')}")
    print()
except Exception as e:
    print(f"✗ 测试失败：{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Solo survival without disasters
solo_world = {
    "name": "孤岛求生",
    "theme": "荒野岛屿",
    "difficulty": "标准",
    "narrative_length": 7,
    "language": "中文",
    "genre_contract": "3",
    "setting": {
        "safe_base": "废弃灯塔",
        "external_dangers": ["野生动物", "暴雨天气"],
        "exploration_method": "徒步探索岛屿各区域",
        "disaster_cycle": "",
        "disaster_type": "",
    },
    "resources": {
        "primary": ["淡水", "食物", "木材", "石材", "燃料"],
    },
    "rules": {
        "death": {"type": "checkpoint"},
    },
    "talent": {
        "name": "生存专家",
        "description": "精通野外生存技能",
        "trigger": "当资源低于 20% 时",
        "effect": "获得额外资源",
        "limitations": "每日限用一次",
        "mechanical_effect": "resource_boost",
        "strategic_loop": {
            "input": "资源收集",
            "conversion": "制作生存工具",
            "competitive_impact": "延长存活天数",
            "counterplay": "环境恶化加速资源消耗",
        },
        "opening_card": {
            "advantage": "初始拥有打火石",
            "first_use": "第一个夜晚点燃篝火",
            "comparison": "比无天赋者多存活 50%",
            "hard_limit": "无法在室内使用",
        },
        "rarity": "B",
    },
    "world_blueprint": {
        "locations": [
            {"id": "lighthouse", "name": "废弃灯塔", "safe": True, "discovered": True},
            {"id": "beach", "name": "海滩", "safe": False, "discovered": True},
            {"id": "forest", "name": "丛林", "safe": False, "discovered": False},
        ],
        "starting_location": "lighthouse",
        "enemies": [{"id": "wild_boar", "name": "野猪", "damage": 5}],
        "areas": [{"id": "beach_area", "name": "海滩区域", "location_id": "beach"}],
        "modules": [{"id": "fire_pit", "name": "篝火"}],
        "recipes": [{"id": "make_fire", "name": "生火", "materials": {"木材": 5}}],
        "action_targets": [{"id": "explore"}],
        "npcs": [],
        "factions": [],
        "relationships": [],
        "starting_inventory": {
            "resources": {"淡水": 10, "食物": 10},
            "equipment": [{"id": "knife", "durability": 10}],
            "items": [],
        },
        "event_pool": [
            {"id": "evt_001", "type": "FIND_WATER"},
            {"id": "evt_002", "type": "ENCOUNTER_ANIMAL"},
            {"id": "evt_003", "type": "WEATHER_EVENT"},
        ],
        "creative_slots": {},
        "motifs": ["孤独", "坚韧", "重生"],
        "taboo_domains": [],
    }
}

try:
    print("测试 2: 单人求生无灾难模式...")
    world2, talent2 = normalize_package({"world": {}, "player_talent": {}}, solo_world)
    print(f"✓ 世界创建成功：{world2['name']}")
    print(f"  Genre: {world2.get('genre_contract', {}).get('id')}")
    print(f"  安全基地：{world2['setting'].get('safe_base')}")
    print(f"  灾难周期：{world2['setting'].get('disaster_cycle')}")
    print()
except Exception as e:
    print(f"✗ 测试失败：{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 50)
print("✓ 所有测试通过！P0-4 修复生效。")
print("=" * 50)
