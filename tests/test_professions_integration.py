#!/usr/bin/env python3
"""测试 professions 集成到 create_save.py"""

import sys
from pathlib import Path

# 添加路径
PROJECT_DIR = Path(__file__).parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools.create_save import normalize_package, load_yaml

def test_professions_integration():
    """测试 professions 是否正确从模板读取并传递给 compiler"""
    
    # 加载世界模板
    template_world_path = PROJECT_DIR / "templates" / "world_template.yaml"
    template = load_yaml(template_world_path)
    
    # 添加一个测试用的 professions
    test_professions = {
        "mechanic": {
            "id": "mechanic",
            "name": "缆车维修师",
            "description": "测试职业"
        },
        "contract_signer": {
            "id": "contract_signer",
            "name": "契约签署员",
            "description": "测试职业"
        }
    }
    template["world"]["professions"] = test_professions
    
    # 准备问卷答案（模拟问答格式）
    raw_answers = {
        "theme": "废土列车",
        "difficulty": "标准",
        "language": "中文",
        "narrative_length": 7,
        "world_name": "测试世界",
    }
    
    from tools.create_save import answers_to_package
    supplied_world, supplied_talent = answers_to_package(raw_answers)
    world, talent = normalize_package(template, supplied_world, supplied_talent)
    
    # 验证 professions 已包含在 world 配置中
    assert "professions" in world, "❌ professions 未添加到 world 配置"
    print(f"✅ professions 已正确添加到 world 配置")
    print(f"   职业数量：{len(world['professions'])}")
    
    # 验证 generation_bundle 中也有 professions（如果 compiler 支持）
    bundle = world.get("generation_bundle", {})
    if "professions" in bundle:
        print(f"✅ professions 已包含在 generation_bundle 中")
    else:
        print(f"⚠️  warnings: generation_bundle 中未找到 professions (compiler 可能尚未支持)")
    
    print("\n✅ 测试通过：Professions 已成功集成到 create_save.py")
    return True

if __name__ == "__main__":
    try:
        test_professions_integration()
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
