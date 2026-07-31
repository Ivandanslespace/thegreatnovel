"""Autoplay Suite - 批量自动化测试运行器

一次性运行多个存档 × 多个策略的组合测试。

用法:
    python tools/autoplay_suite.py --save saves/锈铁方舟 --turns 50 --policies abc,random
    
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Get CPU core count for parallel execution
def get_max_workers():
    try:
        import multiprocessing
        return multiprocessing.cpu_count()
    except:
        return 4


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
        output_dir = f"autoplay_runs/{output_prefix}_{timestamp}"
    
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
        
        # CRITICAL: Read exit_code from run.json instead of just returncode
        exit_code = result.returncode
        has_p0 = False
        status = "success"
        
        run_json_path = Path(output_dir) / "run.json"
        if run_json_path.exists():
            try:
                with open(run_json_path, "r", encoding="utf-8") as f:
                    run_data = json.load(f)
                    exit_code = run_data.get("exit_code", exit_code)
                    has_p0 = run_data.get("has_p0_issues", False)
            except:
                pass
        
        # Map exit codes to proper statuses
        if exit_code == 0:
            status = "success"
        elif exit_code == 2:
            # Completed but has P0 issues
            status = "p0_issues"
        elif exit_code == 3:
            # Crashed
            status = "crashed"
        elif exit_code == 4:
            # Initialization failed
            status = "init_failed"
        else:
            status = "failed"
        
        return {
            "status": status,
            "exit_code": exit_code,
            "has_p0": has_p0,
            "output_dir": output_dir,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "policy": policy,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "output_dir": output_dir,
            "error": "超时 (5 分钟)",
            "policy": policy,
        }


def generate_summary_report(results: List[dict], args) -> str:
    """生成汇总报告"""
    
    lines = []
    lines.append("# Autoplay Suite Summary Report\n")
    lines.append(f"**时间**: {datetime.now().isoformat()}\n")
    lines.append(f"**配置**: {args.save} × {args.turns} 轮 × {len(args.policies)} 策略\n\n")
    
    # 总体统计
    total = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    p0_issues_count = sum(1 for r in results if r["status"] == "p0_issues")
    crashed = sum(1 for r in results if r["status"] == "crashed")
    init_failed = sum(1 for r in results if r["status"] == "init_failed")
    failed = sum(1 for r in results if r["status"] == "failed")
    timeout = sum(1 for r in results if r["status"] == "timeout")
    
    lines.append("## 总体统计\n")
    lines.append(f"- 总运行数：{total}\n")
    lines.append(f"- ✅ 成功：{success}\n")
    lines.append(f"- 🔴 P0 问题：{p0_issues_count}\n")
    lines.append(f"- 🩸 崩溃：{crashed}\n")
    lines.append(f"- 🚫 初始化失败：{init_failed}\n")
    lines.append(f"- ❌ 其他失败：{failed}\n")
    lines.append(f"- ⏱️ 超时：{timeout}\n\n")
    
    # 详细结果
    lines.append("## 详细结果\n")
    
    for i, result in enumerate(results):
        if result["status"] == "success":
            status_icon = "✅"
        elif result["status"] == "p0_issues":
            status_icon = "🔴"
        elif result["status"] == "crashed":
            status_icon = "🩸"
        elif result["status"] == "init_failed":
            status_icon = "🚫"
        elif result["status"] == "failed":
            status_icon = "❌"
        else:
            status_icon = "⏱️"
        
        lines.append(f"### {i+1}. {status_icon} {result.get('policy', 'unknown')}\n")
        lines.append(f"- 状态：{result['status']}\n")
        lines.append(f"- Exit Code: {result.get('exit_code', 'N/A')}\n")
        lines.append(f"- 输出：{result.get('output_dir', 'N/A')}\n")
        
        if result["status"] != "success":
            lines.append(f"- 错误：{result.get('error', result.get('stderr', '未知'))}\n")
        
        lines.append("\n")
    
    # P0 问题汇总
    lines.append("## P0 问题检测\n")
    
    p0_runs = [r for r in results if r.get("has_p0", False)]
    
    if p0_runs:
        lines.append(f"发现 **{len(p0_runs)}** 个运行存在 P0 问题:\n\n")
        
        for issue in p0_runs[:5]:
            output_dir = issue.get('output_dir')
            report_path = Path(output_dir) / "report.md" if output_dir else None
            
            details = ""
            if report_path and report_path.exists():
                content = report_path.read_text(encoding="utf-8", errors='ignore')
                p0_lines = [l for l in content.split('\n') if '[P0]' in l]
                details = "\n".join(p0_lines[:3]) + "\n\n" if p0_lines else ""
            
            lines.append(f"⚠️ **{issue['policy']}**\n")
            lines.append(f"{details}")
            lines.append(f"报告路径：`{output_dir}/report.md`\n\n")
    else:
        lines.append("未发现 P0 级问题！✅\n\n")
    
    # 建议
    lines.append("## 建议\n")
    
    if crashed > 0:
        lines.append(f"- ❗ **关键修复**: {crashed} 个运行崩溃，需立即修复\n\n")
    
    if p0_issues_count > 0:
        lines.append(f"- ❗ **机制问题**: {p0_issues_count} 个运行存在 P0 问题\n")
        lines.append("  建议执行以下命令查看详细报告:\n\n")
        for issue in p0_runs[:3]:
            output_dir = issue.get('output_dir')
            if output_dir:
                lines.append(f"  ```bash\n")
                lines.append(f"  cat {output_dir}/report.md\n")
                lines.append(f"  ```\n\n")
    
    if failed > 0 or timeout > 0:
        lines.append(f"- ⚠️ 有 {failed + timeout} 个运行失败/超时，请检查日志\n\n")
    
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
    
    # Run all combinations with parallel execution
    max_workers = args.max_workers or get_max_workers()
    print(f"🚀 开始批量测试 (并行度={max_workers})...\n")
    
    results = []
    
    if max_workers > 1:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_policy = {
                executor.submit(
                    run_single_test,
                    save_dir=args.save,
                    turns=args.turns,
                    policy=policy,
                    seed=args.seed,
                    output_prefix=prefix,
                ): policy
                for policy in policies
            }
            
            for future in as_completed(future_to_policy):
                result = future.result()
                results.append(result)
                
                # Print feedback
                status_icon = {
                    "success": "✅",
                    "p0_issues": "🔴",
                    "crashed": "🩸",
                    "init_failed": "🚫",
                    "failed": "❌",
                    "timeout": "⏱️",
                }.get(result["status"], "?")
                
                print(f"  {status_icon} {result['policy']}: {result['status']} (exit={result.get('exit_code', 'N/A')})\n")
    else:
        # Sequential execution
        for policy in policies:
            result = run_single_test(
                save_dir=args.save,
                turns=args.turns,
                policy=policy,
                seed=args.seed,
                output_prefix=prefix,
            )
            results.append(result)
            
            status_icon = {
                "success": "✅",
                "p0_issues": "🔴",
                "crashed": "🩸",
                "init_failed": "🚫",
                "failed": "❌",
                "timeout": "⏱️",
            }.get(result["status"], "?")
            
            print(f"  {status_icon} {result['policy']}: {result['status']} (exit={result.get('exit_code', 'N/A')})\n")
    
    # Generate summary report
    print(f"\n📊 生成汇总报告...")
    
    summary_markdown = generate_summary_report(results, args)
    
    summary_file = Path("autoplay_runs") / f"{prefix}_summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write(summary_markdown)
    
    print(f"\n✅ 完成！\n")
    print(f"== 汇总 ==\n")
    
    success = sum(1 for r in results if r["status"] == "success")
    p0_issues_count = sum(1 for r in results if r["status"] == "p0_issues")
    crashed = sum(1 for r in results if r["status"] == "crashed")
    init_failed = sum(1 for r in results if r["status"] == "init_failed")
    failed = sum(1 for r in results if r["status"] == "failed")
    timeout = sum(1 for r in results if r["status"] == "timeout")
    
    print(f"总运行：{len(results)}")
    print(f"成功：{success}")
    print(f"P0 问题：{p0_issues_count}")
    print(f"崩溃：{crashed}")
    print(f"其他失败：{failed + init_failed + timeout}\n")
    
    print(f"汇总报告：`{summary_file.absolute()`}\n")
    
    # Exit code based on most critical issue
    if crashed > 0:
        sys.exit(3)  # Crashed
    elif p0_issues_count > 0:
        sys.exit(2)  # Has P0 issues
    elif failed + init_failed + timeout > 0:
        sys.exit(1)  # Other failures
    else:
        sys.exit(0)  # All successful


if __name__ == "__main__":
    main()
