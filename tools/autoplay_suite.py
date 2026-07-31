"""Autoplay Suite - 批量自动化测试运行器

一次性运行多个存档 × 多个策略的组合测试。

用法:
    python tools/autoplay_suite.py --runs 4 --turns 50
    
选项:
    --save           测试存档目录 (默认使用 saves/锈铁方舟)
    --turns          每局回合数 (默认 50)
    --runs           并行运行数量 (默认根据 CPU 核心数)
    --policies       策略列表，逗号分隔 (默认 abc,random,aggressive,builder)

输出:
    autoplay_runs/
        └── suite_2026-07-31/
            ├── run_xxx/           # 每个子运行
            │   ├── report.md
            │   └── ...
            └── summary_report.md   # 汇总报告
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def run_single_test(
    save_dir: str,
    turns: int,
    policy: str,
    seed: int = 42,
    output_prefix: str = None,
) -> dict:
    """运行单个测试并返回结果字典"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_prefix:
        output_dir = f"autoplay_runs/{output_prefix}_{policy}_{timestamp}"
    else:
        output_dir = f"autoplay_runs/{timestamp}_{policy}"
    
    cmd = [
        sys.executable,
        "tools/autoplay_test.py",
        "--save", save_dir,
        "--turns", str(turns),
        "--policy", policy,
        "--output", output_dir,
    ]
    
    if policy == "random":
        cmd.extend(["--seed", str(seed)])
    
    print(f"🎮 运行：{policy} on {os.path.basename(save_dir)} ({turns} 轮)")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        success = result.returncode == 0
        
        return {
            "status": "success" if success else "failed",
            "output_dir": output_dir,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "output_dir": output_dir,
            "error": "超时 (5 分钟)",
        }


def generate_summary_report(results: List[dict], args) -> str:
    """生成汇总报告"""
    
    lines = []
    lines.append("# Autoplay Suite Summary Report\n")
    lines.append(f"**时间**: {datetime.now().isoformat()}\n")
    lines.append(f"**配置**: {args.turns} 轮 × {len(args.policies)} 策略\n\n")
    
    # 总体统计
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    timeout = sum(1 for r in results if r["status"] == "timeout")
    
    lines.append("## 总体统计\n")
    lines.append(f"- 总运行数：{total}\n")
    lines.append(f"- 成功：{success}\n")
    lines.append(f"- 失败：{failed}\n")
    lines.append(f"- 超时：{timeout}\n\n")
    
    # 详细结果
    lines.append("## 详细结果\n")
    
    for i, result in enumerate(results):
        status_icon = "✅" if result["status"] == "success" else "❌" if result["status"] == "failed" else "⏱️"
        
        lines.append(f"### {i+1}. {status_icon} {result.get('policy', 'unknown')}\n")
        lines.append(f"- 状态：{result['status']}\n")
        lines.append(f"- 输出：{result.get('output_dir', 'N/A')}\n")
        
        if result["status"] != "success":
            lines.append(f"- 错误：{result.get('error', result.get('stderr', '未知'))}\n")
        
        lines.append("\n")
    
    # 快速检查常见问题
    lines.append("## P0 问题检测\n")
    
    p0_issues = []
    
    for result in results:
        if result["status"] != "success":
            continue
        
        output_dir = result.get("output_dir")
        if not output_dir or not Path(output_dir).exists():
            continue
        
        report_path = Path(output_dir) / "report.md"
        if report_path.exists():
            content = report_path.read_text(encoding="utf-8")
            
            # 简单搜索 P0
            p0_count = content.count("### 🔴 [P0]")
            
            if p0_count > 0:
                p0_issues.append({
                    "run": result.get("policy"),
                    "count": p0_count,
                    "output_dir": output_dir,
                })
    
    if p0_issues:
        lines.append(f"发现 {len(p0_issues)} 个运行存在 P0 问题:\n\n")
        
        for issue in p0_issues:
            lines.append(f"⚠️ **{issue['run']}**: {issue['count']} 个 P0 问题\n")
            lines.append(f"   报告路径：{issue['output_dir']}/report.md\n\n")
    else:
        lines.append("未发现 P0 级问题！\n\n")
    
    # 建议
    lines.append("## 建议\n")
    
    if failed > 0:
        lines.append(f"- ❗ 有 {failed} 个运行失败，请检查 stderr 日志\n\n")
    
    if p0_issues:
        lines.append(f"- ❗ 有 {len(p0_issues)} 个运行发现 P0 问题，需优先修复\n")
        lines.append("  建议执行以下命令查看详细报告:\n\n")
        for issue in p0_issues[:3]:  # 只显示前 3 个
            lines.append(f"  ```bash\n")
            lines.append(f"  cat {issue['output_dir']}/report.md\n")
            lines.append(f"  ```\n\n")
    
    lines.append("- ℹ️ 所有原始数据保存在 `autoplay_runs/` 目录\n")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Autoplay Suite - 批量测试")
    parser.add_argument("--save", type=str, default="saves/锈铁方舟", help="测试存档")
    parser.add_argument("--turns", type=int, default=50, help="每局回合数")
    parser.add_argument("--policies", type=str, default="abc,random,aggressive,builder",
                        help="策略列表，逗号分隔")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--prefix", type=str, default=None, help="输出目录前缀")
    parser.add_argument("--max-workers", type=int, default=None, help="最大并行度")
    
    args = parser.parse_args()
    
    # 验证存档
    save_path = Path(args.save)
    if not save_path.exists():
        print(f"❌ 存档不存在：{args.save}")
        sys.exit(1)
    
    # 解析策略
    policies = [p.strip() for p in args.policies.split(",")]
    
    if not policies:
        print("❌ 无有效策略")
        sys.exit(1)
    
    print(f"\n📋 配置:")
    print(f"  存档：{args.save}")
    print(f"  回合数：{args.turns}")
    print(f"  策略：{', '.join(policies)}")
    print(f"  随机种子：{args.seed}\n")
    
    # 确保输出目录存在
    Path("autoplay_runs").mkdir(exist_ok=True)
    
    # 生成唯一前缀
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = args.prefix or f"suite_{timestamp}"
    
    # 运行所有组合
    print(f"🚀 开始批量测试...\n")
    
    results = []
    
    for policy in policies:
        result = run_single_test(
            save_dir=args.save,
            turns=args.turns,
            policy=policy,
            seed=args.seed,
            output_prefix=prefix,
        )
        result["policy"] = policy
        results.append(result)
        
        # 打印简要反馈
        status_icon = "✅" if result["status"] == "success" else "❌" if result["status"] == "failed" else "⏱️"
        print(f"  {status_icon} {policy}: {result['status']}\n")
    
    # 生成汇总报告
    print(f"\n📊 生成汇总报告...")
    
    summary_markdown = generate_summary_report(results, args)
    
    summary_file = Path("autoplay_runs") / f"{prefix}_summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary_markdown)
    
    print(f"\n✅ 完成！\n")
    print(f"== 汇总 ==")
    print(f"  总运行：{len(results)}")
    print(f"  成功：{sum(1 for r in results if r['status'] == 'success')}")
    print(f"  失败：{sum(1 for r in results if r['status'] == 'failed')}")
    print(f"\n汇总报告：{summary_file.absolute()}")
    
    # 退出码
    failed = sum(1 for r in results if r["status"] != "success")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
