#!/usr/bin/env python3
"""Autoplay New World - 从主题到自动游玩的完整编排

用法：
    # 使用已有存档
    python tools/autoplay_new_world.py saves/锈铁方舟 --turns 50 --policy abc
    
    # 使用 YAML 文件创建新世界并 autoplay
    python tools/autoplay_new_world.py temps/punk_world.yaml --turns 50 --policy random
    
    # 如果 target 是目录，直接 autoplay；如果是 YAML 文件，先创建存档再 autoplay
    
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
import uuid

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools.validate_save import run_validation


def main():
    parser = argparse.ArgumentParser(description="Autoplay New World - 创建新世界并自动游玩")
    parser.add_argument("target", help="目标：YAML 世界配置文件或已有存档路径 (如'saves/锈铁方舟')")
    parser.add_argument("--turns", type=int, default=50, help="自动游玩轮数")
    parser.add_argument("--policy", type=str, default="abc", choices=["abc", "random", "aggressive", "builder"],
                        help="策略类型")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--save-root", default="saves", help="存档根目录")
    
    args = parser.parse_args()
    
    target_path = Path(args.target)
    save_root = Path(args.save_root)
    
    # Case 1: 如果 target 是 YAML 文件 → 创建存档然后 autoplay
    if target_path.is_file() and target_path.suffix in ['.yaml', '.yml']:
        print("=" * 60)
        print("🎮 Autoplay New World - 从 YAML 创建新世界")
        print("=" * 60)
        
        # Step 1: 验证 YAML 文件存在
        print(f"\n📄 步骤 1: 加载 YAML 配置")
        print(f"   文件：{target_path.resolve()}")
        
        import yaml
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                world_data = yaml.safe_load(f)
            print(f"   ✅ YAML 格式正确")
        except Exception as e:
            print(f"   ❌ YAML 解析失败：{e}")
            return 1
        
        # Step 2: 调用 create_save.py 创建存档
        print(f"\n🏗️  步骤 2: 创建存档")
        
        import subprocess
        cmd_create = [
            sys.executable,
            "tools/create_save.py",
            "--answers", str(target_path.resolve()),
            "--save-root", str(save_root),
        ]
        
        print(f"   执行命令:\n   {' '.join(cmd_create)}\n")
        
        result_create = subprocess.run(cmd_create, cwd=PROJECT_DIR)
        
        if result_create.returncode != 0:
            print(f"\n❌ 存档创建失败，exit code: {result_create.returncode}")
            return result_create.returncode
        
        # Step 3: 获取世界名称（从 YAML 中提取）
        world_name = None
        if isinstance(world_data, dict):
            if 'world' in world_data and isinstance(world_data['world'], dict):
                world_name = world_data['world'].get('name')
            elif 'name' in world_data:
                world_name = world_data.get('name')
        
        if not world_name:
            print("\n⚠️  无法从 YAML 中提取世界名称，尝试推断...")
            world_name = target_path.stem
        
        expected_save_path = save_root / world_name
        
        # Step 4: 验证存档已创建
        print(f"\n✅ 步骤 3: 验证存档")
        print(f"   期望路径：{expected_save_path}")
        
        if not expected_save_path.exists():
            print(f"   ⚠️  存档不存在，尝试使用默认路径：{save_root}/punk_world")
            # 尝试常见的命名方式
            for possible_path in [save_root / world_name, save_root / target_path.stem]:
                if possible_path.exists():
                    expected_save_path = possible_path
                    print(f"   找到存档：{expected_save_path}")
                    break
            else:
                print(f"   ❌ 找不到存档文件！")
                print(f"   saves/ 目录下内容:")
                if save_root.exists():
                    for item in save_root.iterdir():
                        print(f"     - {item.name}")
                return 1
        
        save_path = expected_save_path
        
    # Case 2: 如果 target 是有效存档路径 → 直接 autoplay
    elif target_path.exists() and target_path.is_dir():
        print(f"✅ 使用已有存档：{save_path}")
        save_path = target_path
    else:
        print(f"\n❌ 错误：找不到文件或存档：{args.target}")
        return 1
    
    # Case 3: 存档存在 → 运行 autoplay
    print(f"\n🎯 开始自动游玩：{save_path.name}")
    print(f"   回合数：{args.turns}")
    print(f"   策略：{args.policy}")
    
    # 调用 autoplay_test.py
    cmd = [
        sys.executable,
        "tools/autoplay_test.py",
        "--save", str(save_path),
        "--turns", str(args.turns),
        "--policy", args.policy,
        "--seed", str(args.seed),
    ]
    
    print(f"\n🚀 执行命令:\n   {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
