"""Autoplay Test Engine - 自动播放测试系统

完全不需要 LLM API，直接使用 Python import 方式快速测试机制交互。

用法示例:
    # ABC 固定序列测试 (推荐用于回归测试)
    python tools/autoplay_test.py --save saves/锈铁方舟 --turns 50 --policy abc
    
    # 随机策略测试
    python tools/autoplay_test.py --save saves/锈铁方舟 --turns 100 --policy random --seed 42
    
    # 压力测试 (优先战斗/探索)
    python tools/autoplay_test.py --save saves/锈铁方舟 --turns 50 --policy aggressive
    
    # 建造者策略测试
    python tools/autoplay_test.py --save saves/锈铁方舟 --turns 100 --policy builder

输出:
    autoplay_runs/2026-07-31_abc_xxx/
        ├── turns.jsonl         # 每轮详细数据
        ├── run.json            # 汇总统计
        ├── initial_state.json  # 初始状态快照
        ├── final_state.json    # 最终状态快照
        ├── events.json         # 所有事件
        └── report.md           # Markdown 审计报告
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine_runtime.state import load_game_state
from engine_runtime.runtime import GameEngine
from tools.turn_controller import resolve as resolve_turn


class Policy:
    """玩家策略基类"""
    
    def choose(self, turn: int, visible_options: dict[str, dict]) -> Optional[str]:
        """选择选项，返回选项键 (A/B/C) 或 None"""
        raise NotImplementedError


class ABCPolicy(Policy):
    """ABC 循环策略 - 推荐用于回归测试"""
    sequence = ["A", "B", "C"]
    
    def choose(self, turn: int, visible_options: dict[str, dict]) -> Optional[str]:
        preferred = self.sequence[turn % len(self.sequence)]
        
        if preferred in visible_options:
            return preferred
        
        # Fallback: 按优先级选择可用的
        for choice in self.sequence:
            if choice in visible_options:
                return choice
        
        return None


class RandomPolicy(Policy):
    """随机策略 - 需要设置随机 seed"""
    
    def __init__(self, seed: int = 42):
        import random
        self.random = random.Random(seed)
    
    def choose(self, turn: int, visible_options: dict[str, dict]) -> Optional[str]:
        if not visible_options:
            return None
        
        options = list(visible_options.keys())
        return self.random.choice(options)


class AggressivePolicy(Policy):
    """激进策略 - 优先战斗/探索/高风险行动"""
    
    HIGH_RISK_TYPES = {"COMBAT", "EXPLORATION", "TRAVEL", "EXTRACTION"}
    
    def choose(self, turn: int, visible_options: dict[str, dict]) -> Optional[str]:
        if not visible_options:
            return None
        
        # 检查每个选项的类型
        for key, opt in visible_options.items():
            action = opt.get("action", {})
            action_type = str(action.get("type", ""))
            if action_type in self.HIGH_RISK_TYPES:
                return key
        
        # Fallback
        return next(iter(visible_options.keys()), None)


class BuilderPolicy(Policy):
    """建造者策略 - 优先基地发展和社会互动"""
    
    PRIORITY_TYPES = {"BUILD", "BASE_MANAGEMENT", "SOCIAL_INTERACTION", "RESEARCH", "TRADE"}
    
    def choose(self, turn: int, visible_options: dict[str, dict]) -> Optional[str]:
        if not visible_options:
            return None
        
        # 检查每个选项的类型
        for key, opt in visible_options.items():
            action = opt.get("action", {})
            action_type = str(action.get("type", ""))
            if action_type in self.PRIORITY_TYPES:
                return key
        
        # Fallback
        return next(iter(visible_options.keys()), None)


class TelemetryRecorder:
    """遥测记录器 - 捕获每轮详细数据"""
    
    def __init__(self):
        self.turns: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
    
    def record_turn(
        self,
        turn: int,
        decision: int,
        requested_choice: Optional[str],
        actual_choice: Optional[str],
        reason_fallback: Optional[str],
        before: Dict[str, Any],
        options_before: Dict[str, str],
        result: Dict[str, Any],
        after: Dict[str, Any],
        events_created: List[Dict[str, Any]],
    ) -> None:
        self.turns.append({
            "decision": decision,
            "turn": turn,
            "requested_choice": requested_choice,
            "actual_choice": actual_choice,
            "reason_fallback": reason_fallback,
            "before": before,
            "options_before": options_before,
            "result": result,
            "after": after,
            "events_created": [dict(e) for e in events_created],
            "warnings": [],
        })
        
        # 收集事件
        self.events.extend(events_created)
    
    def add_warning(self, level: str, category: str, message: str) -> None:
        self.warnings.append({
            "level": level,  # P0/P1/P2
            "category": category,
            "message": message,
        })
    
    def to_jsonl(self) -> str:
        """导出为 JSONL 格式"""
        lines = []
        for turn in self.turns:
            lines.append(json.dumps(turn, ensure_ascii=False))
        return "\n".join(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取摘要统计"""
        return {
            "total_turns": len(self.turns),
            "total_events": len(self.events),
            "total_warnings": len(self.warnings),
            "warnings_by_level": self._count_by_level(),
        }
    
    def _count_by_level(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for w in self.warnings:
            level = w["level"]
            counts[level] = counts.get(level, 0) + 1
        return counts


class AutoAuditor:
    """自动审计器 - 检测潜在问题"""
    
    def __init__(self, telemetry: TelemetryRecorder):
        self.telemetry = telemetry
    
    def audit(self) -> List[Dict[str, Any]]:
        """运行全部审计规则"""
        findings = []
        
        # 1. 死局检测
        findings.extend(self._detect_stuck_loop())
        
        # 2. 无合法出口检测
        findings.extend(self._detect_no_action())
        
        # 3. 时间停滞检测
        findings.extend(self._detect_time_stopped())
        
        # 4. 异常时间跳跃检测
        findings.extend(self._detect_time_jump())
        
        # 5. 机制覆盖率检测
        findings.extend(self._detect_mechanism_coverage())
        
        # 6. 未退出机制检测
        findings.extend(self._detect_unclosed_mechanisms())
        
        # 7. 公共系统活跃检测
        findings.extend(self._detect_public_system_dormant())
        
        # 8. 选项多样性检测
        findings.extend(self._detect_option_diversity())
        
        # 9. ABC 质量检测
        findings.extend(self._detect_abc_quality())
        
        # 10. 结果分布检测
        findings.extend(self._detect_result_distribution())
        
        return findings
    
    def _detect_stuck_loop(self) -> List[Dict[str, Any]]:
        """检测连续重复选项的死循环"""
        findings = []
        
        same_count = 0
        last_action = None
        
        for turn in self.telemetry.turns:
            action_type = turn["result"].get("action_type", "")
            
            if action_type == last_action:
                same_count += 1
            else:
                same_count = 1
                last_action = action_type
            
            if same_count >= 5:
                findings.append({
                    "level": "P1",
                    "category": "STUCK_LOOP",
                    "message": f"连续 {same_count} 轮执行相同类型行动：{action_type}",
                    "turn_range": (max(1, turn["decision"] - same_count + 1), turn["decision"]),
                })
                break  # 只报告一次
        
        return findings
    
    def _detect_no_action(self) -> List[Dict[str, Any]]:
        """检测没有可用行动的情况"""
        findings = []
        
        for turn in self.telemetry.turns:
            options = turn["options_before"]
            if not options:
                findings.append({
                    "level": "P0",
                    "category": "NO_AVAILABLE_ACTION",
                    "message": f"决策 {turn['decision']} 无任何可选选项",
                    "turn": turn["decision"],
                })
        
        return findings
    
    def _detect_time_stopped(self) -> List[Dict[str, Any]]:
        """检测零时间行动无限循环"""
        findings = []
        
        consecutive_zero_time = []
        
        for turn in self.telemetry.turns:
            result = turn["result"]
            time_cost = float(result.get("time_cost", 0) or 0)
            
            if time_cost == 0:
                consecutive_zero_time.append(turn["decision"])
            else:
                if len(consecutive_zero_time) >= 10:
                    findings.append({
                        "level": "P0",
                        "category": "TIME_NOT_ADVANCING",
                        "message": f"{len(consecutive_zero_time)} 次零时间行动连续执行",
                        "decisions": consecutive_zero_time[:10],  # 只显示前 10 个
                    })
                consecutive_zero_time = []
        
        # 检查末尾
        if len(consecutive_zero_time) >= 10:
            findings.append({
                "level": "P0",
                "category": "TIME_NOT_ADVANCING",
                "message": f"{len(consecutive_zero_time)} 次零时间行动在末尾连续执行",
                "decisions": consecutive_zero_time[:10],
            })
        
        return findings
    
    def _detect_time_jump(self) -> List[Dict[str, Any]]:
        """检测异常的时间跳跃"""
        findings = []
        
        prev_day_elapsed = 0
        
        for turn in self.telemetry.turns:
            after = turn["after"]
            day_elapsed = float(after.get("day_elapsed_minutes", 0) or 0)
            
            jump = abs(day_elapsed - prev_day_elapsed)
            
            # 超过 2 小时的跳跃视为异常
            if jump > 120:
                findings.append({
                    "level": "P1",
                    "category": "TIME_JUMP_ANOMALY",
                    "message": f"决策 {turn['decision']} 出现异常时间跳跃：+{jump:.0f}分钟",
                    "turn": turn["decision"],
                    "before": prev_day_elapsed,
                    "after": day_elapsed,
                })
            
            prev_day_elapsed = day_elapsed
        
        return findings
    
    def _detect_mechanism_coverage(self) -> List[Dict[str, Any]]:
        """检测机制是否被触发"""
        findings = []
        
        mechanism_counts: Dict[str, int] = {}
        
        for turn in self.telemetry.turns:
            action_type = turn["result"].get("action_type", "UNKNOWN")
            mechanism_counts[action_type] = mechanism_counts.get(action_type, 0) + 1
        
        # 某些重要机制应该被触发
        important_mechanisms = ["COMBAT", "EXPLORATION", "BUILD", "SOCIAL_INTERACTION"]
        
        for mech in important_mechanisms:
            if mechanism_counts.get(mech, 0) == 0:
                findings.append({
                    "level": "P1",
                    "category": "MECHANISM_UNREACHABLE",
                    "message": f"50 轮内从未触发：{mech}",
                    "mechanism": mech,
                    "expected": True,
                })
        
        return findings
    
    def _detect_unclosed_mechanisms(self) -> List[Dict[str, Any]]:
        """检测未退出的机制 (如 encounter)"""
        findings = []
        
        active_encounter = None
        
        for turn in self.telemetry.turns:
            after = turn["after"]
            current_encounter = after.get("current_encounter_id")
            
            if current_encounter and not active_encounter:
                active_encounter = {
                    "encounter_id": current_encounter,
                    "entered_at": turn["decision"],
                }
            elif not current_encounter and active_encounter:
                findings.append({
                    "level": "P0",
                    "category": "ENCOUNTER_OPEN_END",
                    "message": f"Encounter {active_encounter['encounter_id']} 在第 {active_encounter['entered_at']} 轮进入，但未检测到退出事件",
                    "encounter_id": active_encounter["encounter_id"],
                    "entered_at": active_encounter["entered_at"],
                })
                active_encounter = None
        
        # 检查结束时的状态
        if active_encounter:
            findings.append({
                "level": "P0",
                "category": "ENCOUNTER_STILL_ACTIVE",
                "message": f"Encounter {active_encounter['encounter_id']} 在游戏结束时仍未退出",
                "encounter_id": active_encounter["encounter_id"],
                "entered_at": active_encounter["entered_at"],
                "still_active_after": len(self.telemetry.turns),
            })
        
        return findings
    
    def _detect_public_system_dormant(self) -> List[Dict[str, Any]]:
        """检测公共系统是否活跃"""
        findings = []
        
        public_advances = 0
        peer_actions = 0
        
        for turn in self.telemetry.turns:
            result = turn["result"]
            
            if "public_feedback" in result:
                public_advances += 1
            
            # 检查事件中的 peer 行动
            for event in turn.get("events_created", []):
                if event.get("type") == "PEER_ACTION_EXECUTED":
                    peer_actions += 1
        
        # 如果至少推进了 10 轮但 peer 行动为 0
        if public_advances >= 10 and peer_actions == 0:
            findings.append({
                "level": "P0",
                "category": "PUBLIC_SYSTEM_PEER_DORMANT",
                "message": f"公共系统推进 {public_advances} 轮，但同行代理行动数为 0",
                "public_advances": public_advances,
                "peer_actions": peer_actions,
            })
        
        return findings
    
    def _detect_option_diversity(self) -> List[Dict[str, Any]]:
        """检测选项多样性"""
        findings = []
        
        option_labels = []
        
        for turn in self.telemetry.turns:
            options = turn["options_before"]
            for key, label in options.items():
                option_labels.append(f"{key}: {label}")
        
        unique_labels = set(option_labels)
        total_labels = len(option_labels)
        
        repetition_rate = 1 - (len(unique_labels) / total_labels) if total_labels > 0 else 0
        
        if repetition_rate > 0.6:  # 超过 60% 的重复
            findings.append({
                "level": "P2",
                "category": "HIGH_OPTION_REPETITION",
                "message": f"选项重复率过高：{repetition_rate*100:.1f}%",
                "repetition_rate": repetition_rate,
                "unique_labels": len(unique_labels),
                "total_labels": total_labels,
            })
        
        return findings
    
    def _detect_abc_quality(self) -> List[Dict[str, Any]]:
        """检测 A/B/C 三个位置的可用性"""
        findings = []
        
        count_a = 0
        count_b = 0
        count_c = 0
        
        for turn in self.telemetry.turns:
            options = turn["options_before"]
            if "A" in options:
                count_a += 1
            if "B" in options:
                count_b += 1
            if "C" in options:
                count_c += 1
        
        total = len(self.telemetry.turns)
        
        # C 位置太不常见
        if count_c < total * 0.3:  # 少于 30%
            findings.append({
                "level": "P1",
                "category": "OPTION_C_UNAVAILABLE_TOO_OFTEN",
                "message": f"C 位置仅出现 {count_c}/{total} 次 ({count_c/total*100:.1f}%)",
                "count_c": count_c,
                "total": total,
            })
        
        # B 位置也太少
        if count_b < total * 0.5:  # 少于 50%
            findings.append({
                "level": "P2",
                "category": "OPTION_B_UNAVAILABLE",
                "message": f"B 位置仅出现 {count_b}/{total} 次 ({count_b/total*100:.1f}%)",
                "count_b": count_b,
                "total": total,
            })
        
        return findings
    
    def _detect_result_distribution(self) -> List[Dict[str, Any]]:
        """检测结果分布是否符合预期"""
        findings = []
        
        outcome_counts: Dict[str, int] = {}
        
        for turn in self.telemetry.turns:
            outcome = turn["result"].get("outcome", "UNKNOWN")
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        
        total = len(self.telemetry.turns)
        
        # 严重失败比例应该很低
        severe_failure_pct = outcome_counts.get("严重失败", 0) / total * 100
        if severe_failure_pct > 15:  # 超过 15%
            findings.append({
                "level": "P2",
                "category": "HIGH_SEVERE_FAILURE_RATE",
                "message": f"严重失败比例过高：{severe_failure_pct:.1f}%",
                "outcome_counts": outcome_counts,
                "severe_failure_pct": severe_failure_pct,
            })
        
        return findings


def create_policy(policy_name: str, seed: int = 42) -> Policy:
    """创建策略实例"""
    policies = {
        "abc": ABCPolicy,
        "random": lambda: RandomPolicy(seed),
        "aggressive": AggressivePolicy,
        "builder": BuilderPolicy,
    }
    
    if policy_name not in policies:
        raise ValueError(f"未知策略：{policy_name}. 可用选项：{list(policies.keys())}")
    
    return policies[policy_name]()


def main():
    parser = argparse.ArgumentParser(description="Autoplay Test Engine")
    parser.add_argument("--save", type=str, required=True, help="存档目录")
    parser.add_argument("--turns", type=int, default=50, help="模拟回合数")
    parser.add_argument("--policy", type=str, default="abc", choices=["abc", "random", "aggressive", "builder"],
                        help="玩家策略")
    parser.add_argument("--seed", type=int, default=42, help="随机种子 (仅 random 策略)")
    parser.add_argument("--output", type=str, default=None, help="输出目录 (默认自动生成)")
    
    args = parser.parse_args()
    
    # 创建临时工作区
    base_path = Path(args.save)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path("autoplay_runs") / f"{timestamp}_{args.policy}"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    temp_save_dir = output_dir / "temp_save"
    
    # 复制存档到临时目录
    print(f"📁 复制存档：{base_path} → {temp_save_dir}")
    if temp_save_dir.exists():
        shutil.rmtree(temp_save_dir)
    shutil.copytree(base_path, temp_save_dir)
    
    # 初始化遥测
    telemetry = TelemetryRecorder()
    
    # 加载游戏状态
    print(f"🎮 开始模拟 {args.turns} 轮...")
    try:
        state = load_game_state(temp_save_dir)
        engine = GameEngine(state)
        
        for decision in range(1, args.turns + 1):
            policy = create_policy(args.policy, args.seed)
            
            # 生成选项
            result = resolve_turn(engine, "", None, generate_options_only=True)
            
            if "error" in result or "visible_options" not in result:
                telemetry.add_warning("P0", "OPTIONS_GENERATION_FAILED", 
                                     f"决策 {decision}: {result.get('error', '未知错误')}")
                break
            
            visible_options = result.get("visible_options", {})
            option_labels = {k: v.get("label", "") for k, v in visible_options.items()}
            
            # 选择选项
            requested = policy.choose(decision, visible_options)
            
            if requested is None:
                telemetry.add_warning("P1", "NO_CHOICE_MADE",
                                     f"决策 {decision}: 策略无法选择，可用选项：{list(visible_options.keys())}")
                break
            
            # 执行回合
            before = {
                "turn": engine.state.current_turn,
                "world_turn": engine.state.world_turn,
                "game_day": engine.state.meta.get("game_day"),
                "time_of_day": engine.state.meta.get("time_of_day"),
                "available_time": engine.state.meta.get("available_time_minutes"),
                "location": engine.state.meta.get("current_location"),
                "hp": engine.state.player.get("hp"),
                "mental": engine.state.player.get("mental"),
            }
            
            result = resolve_turn(engine, requested, None)
            
            # 收集数据
            after = {
                "turn": engine.state.current_turn,
                "world_turn": engine.state.world_turn,
                "game_day": engine.state.meta.get("game_day"),
                "time_of_day": engine.state.meta.get("time_of_day"),
                "available_time": engine.state.meta.get("available_time_minutes"),
                "location": engine.state.meta.get("current_location"),
                "hp": engine.state.player.get("hp"),
                "mental": engine.state.player.get("mental"),
            }
            
            events_created = []
            if "resolved" in result:
                resolved = result["resolved"]
                event = resolved.get("event", {})
                if isinstance(event, dict):
                    events_created.append(dict(event))
                events_created.extend(resolved.get("events", []))
            
            telemetry.record_turn(
                turn=engine.state.current_turn,
                decision=decision,
                requested_choice=requested,
                actual_choice=requested,
                reason_fallback=None,
                before=before,
                options_before=option_labels,
                result=result.get("resolved", {}),
                after=after,
                events_created=events_created,
            )
            
            # 进度输出
            if decision % 10 == 0:
                print(f"   决策 {decision}/{args.turns} ✓")
        
    except Exception as e:
        print(f"❌ 异常：{e}")
        import traceback
        traceback.print_exc()
        
        # 保存失败现场
        failure_dir = output_dir / "failure"
        failure_dir.mkdir(exist_ok=True)
        
        with open(failure_dir / "traceback.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        
        sys.exit(1)
    
    # 清理临时文件
    shutil.rmtree(temp_save_dir)
    
    # 运行审计
    print(f"🔍 运行自动审计...")
    auditor = AutoAuditor(telemetry)
    findings = auditor.audit()
    
    # 添加审计报告
    telemetry.warnings.extend(findings)
    
    # 生成报告
    print(f"📊 生成报告...")
    
    # 保存原始数据
    with open(output_dir / "turns.jsonl", "w", encoding="utf-8") as f:
        f.write(telemetry.to_jsonl())
    
    with open(output_dir / "run.json", "w", encoding="utf-8") as f:
        json.dump({
            "summary": telemetry.get_summary(),
            "findings": findings,
            "start_time": timestamp,
            "policy": args.policy,
            "turns": args.turns,
        }, f, ensure_ascii=False, indent=2)
    
    # 生成 Markdown 报告
    report_lines = []
    report_lines.append("# Autoplay Audit Report\n")
    report_lines.append(f"**时间**: {timestamp}\n")
    report_lines.append(f"**策略**: {args.policy}\n")
    report_lines.append(f"**回合数**: {args.turns}\n\n")
    
    # 结果概览
    report_lines.append("## Result\n")
    report_lines.append(f"- 决策完成：{len(telemetry.turns)}/{args.turns}\n")
    report_lines.append(f"- 发现警告：{len(findings)}\n")
    
    p0_count = sum(1 for f in findings if f["level"] == "P0")
    p1_count = sum(1 for f in findings if f["level"] == "P1")
    p2_count = sum(1 for f in findings if f["level"] == "P2")
    
    report_lines.append(f"- P0 问题：{p0_count}\n")
    report_lines.append(f"- P1 问题：{p1_count}\n")
    report_lines.append(f"- P2 问题：{p2_count}\n\n")
    
    # 机制覆盖
    report_lines.append("## Coverage\n")
    mechanism_counts: Dict[str, int] = {}
    for turn in telemetry.turns:
        mech = turn["result"].get("action_type", "UNKNOWN")
        mechanism_counts[mech] = mechanism_counts.get(mech, 0) + 1
    
    for mech, count in sorted(mechanism_counts.items()):
        marker = " ⚠" if count == 0 else ""
        report_lines.append(f"- {mech}: {count}{marker}\n")
    report_lines.append("\n")
    
    # 问题列表
    if findings:
        report_lines.append("## Findings\n\n")
        
        for finding in findings:
            level = finding["level"]
            category = finding["category"]
            message = finding["message"]
            
            icon = "🔴" if level == "P0" else "🟠" if level == "P1" else "🟡"
            report_lines.append(f"### {icon} [{level}] {category}\n")
            report_lines.append(f"{message}\n\n")
    
    # 最终状态
    if telemetry.turns:
        last_turn = telemetry.turns[-1]["after"]
        report_lines.append("## Final State\n")
        report_lines.append(f"- Turn: {last_turn.get('turn')}\n")
        report_lines.append(f"- World Turn: {last_turn.get('world_turn')}\n")
        report_lines.append(f"- Day: {last_turn.get('game_day')}\n")
        report_lines.append(f"- Location: {last_turn.get('location')}\n")
        report_lines.append(f"- HP: {last_turn.get('hp')}\n")
        report_lines.append(f"- Mental: {last_turn.get('mental')}\n\n")
    
    report_text = "\n".join(report_lines)
    
    with open(output_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_text)
    
    # 打印简要摘要
    print(f"\n✅ 完成！输出目录：{output_dir.absolute()}\n")
    print("== 报告摘要 ==")
    print(f"P0 问题：{p0_count}")
    print(f"P1 问题：{p1_count}")
    print(f"P2 问题：{p2_count}")
    
    if p0_count > 0:
        print(f"\n⚠️  发现 {p0_count} 个 P0 级问题，请详细检查！")


if __name__ == "__main__":
    main()
