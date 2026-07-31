"""
测试 P0-3 修复：世界模板零默认值验证
验证新创建的世界不会从模板继承虚假的生存规则
"""
import yaml
import sys
from pathlib import Path


def test_template_has_no_hardcoded_defaults():
    """测试模板中 rules.*字段全部为 null，没有实际 gameplay 参数"""

    template_path = Path(__file__).parent.parent / "templates" / "world_template.yaml"
    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    rules = data["world"]["rules"]

    # 验证所有 rules.*字段都是 null
    assert rules["safe_zone"] is None, "safe_zone 必须为 null"
    assert rules["exploration"] is None, "exploration 必须为 null"
    assert rules["death"] is None, "death 必须为 null"
    assert rules["disaster"] is None, "disaster 必须为 null"
    assert rules["pvp"] is None, "pvp 必须为 null"
    assert rules["progression"] is None, "progression 必须为 null"

    print("✓ 所有 rules.*字段都为 null（零默认值）")


def test_mechanics_capabilities_exists():
    """测试 mechanics 结构存在且为空"""

    template_path = Path(__file__).parent.parent / "templates" / "world_template.yaml"
    with open(template_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    mechanics = data["world"]["mechanics"]

    # 验证 capabilitys 和 rulesets 是空字典
    assert isinstance(mechanics["capabilities"], dict), "capabilities 必须是字典"
    assert len(mechanics["capabilities"]) == 0, "capabilities 应该为空，由 LLM 填充"
    assert isinstance(mechanics["rulesets"], dict), "rulesets 必须是字典"
    assert len(mechanics["rulesets"]) == 0, "rulesets 应该为空，由 LLM 填充"

    print("✓ mechanics.capabilities 和 mechanics.rulesets 均为空字典")


def test_no_hardcoded_gameplay_values():
    """测试模板中没有包含真实游戏数值的占位符"""

    template_path = Path(__file__).parent.parent / "templates" / "world_template.yaml"
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 检查不应存在的硬编码值
    forbidden_patterns = [
        ("每天一次", "探索频率"),
        ("70%", "掉落率"),
        ("7 天", "灾难周期"),
        ("夜间危险×2", "夜间修正"),
        ("每次灾难强度 +10%", "灾难升级"),
    ]

    for pattern, name in forbidden_patterns:
        assert pattern not in content, f"模板中不应包含{pattern}（{name}）"

    print("✓ 无硬编码的游戏数值占位符")


def test_documentation_comments_exist():
    """测试模板中有清晰的注释说明零默认值原则"""

    template_path = Path(__file__).parent.parent / "templates" / "world_template.yaml"
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()

    required_notes = [
        "NOTE",
        "占位符",
        "null",
        "LLM 在创建世界时必须显式定义每个要启用的机制及其参数",
        "防止注入虚假的通用生存规则",
        "能力注册表",
        "capabilities",
        "rulesets",
    ]

    for note in required_notes:
        assert note in content, f"模板应包含注释：{note}"

    print("✓ 文档注释完整")


def main():
    """运行所有测试"""
    tests = [
        test_template_has_no_hardcoded_defaults,
        test_mechanics_capabilities_exists,
        test_no_hardcoded_gameplay_values,
        test_documentation_comments_exist,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: 异常 - {e}")
            failed += 1

    print(f"\n测试结果：{passed}通过，{failed}失败")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✓ 所有测试通过！P0-3 修复验证完成。")
        sys.exit(0)


if __name__ == "__main__":
    main()
