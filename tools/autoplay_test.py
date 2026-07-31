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
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        # P1-3: 修正索引从 (turn-1)%3 开始
        preferred = self.sequence[(turn - 1) % len(self.sequence)]
        
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
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        if not visible_options:
            return None
        
        options = list(visible_options.keys())
        return self.random.choice(options)


class AggressivePolicy(Policy):
    """激进策略 - 优先战斗/探索/高风险行动"""
    
    HIGH_RISK_TYPES = {"COMBAT", "EXPLORATION", "TRAVEL", "EXTRACT", "RETURN_TO_BASE"}
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        if not visible_options:
            return None
        
        # P1-2: 读取 pending_options 中的 action contract
        if isinstance(pending_options, dict) and pending_options.get("options"):
            for key in visible_options.keys():
                opt = pending_options["options"].get(key, {})
                if isinstance(opt, dict):
                    action = opt.get("action", {})
                    if isinstance(action, dict):
                        action_type = str(action.get("type", ""))
                        if action_type in self.HIGH_RISK_TYPES:
                            return key
        
        # Fallback: 优先第一个可用
        return next(iter(visible_options.keys()), None)


class BuilderPolicy(Policy):
    """建造者策略 - 优先基地发展和社会互动"""
    
    PRIORITY_TYPES = {"BUILD", "BASE_MANAGEMENT", "SOCIAL_INTERACTION", "RESEARCH", "TRADE"}
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        if not visible_options:
            return None
        
        # P1-2: 读取 pending_options 中的 action contract
        if isinstance(pending_options, dict) and pending_options.get("options"):
            for key in visible_options.keys():
                opt = pending_options["options"].get(key, {})
                if isinstance(opt, dict):
                    action = opt.get("action", {})
                    if isinstance(action, dict):
                        action_type = str(action.get("type", ""))
                        if action_type in self.PRIORITY_TYPES:
                            return key
        
        # Fallback: 优先第一个可用
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
        encountered_turns = []
        
        for i, turn in enumerate(self.telemetry.turns):
            after = turn["after"]
            current_encounter = after.get("current_encounter_id")
            
            if current_encounter and not active_encounter:
                # 进入新 encounter
                active_encounter = {
                    "encounter_id": current_encounter,
                    "entered_at": turn["decision"],
                    "turn_index": i,
                }
            elif current_encounter and active_encounter:
                # 可能切换或异常
                if current_encounter != active_encounter["encounter_id"]:
                    # 没有经过 None 直接切换到另一个 encounter - 异常
                    findings.append({
                        "level": "P0",
                        "category": "ENCOUNTER_UNEXPECTED_SWITCH",
                        "message": f"Encounter 在未退出当前遭遇时切换到新的 encounter",
                        "from_encounter": active_encounter["encounter_id"],
                        "to_encounter": current_encounter,
                        "at_decision": turn["decision"],
                    })
                    # 更新为新的 encounter
                    active_encounter["encounter_id"] = current_encounter
                    active_encounter["entered_at"] = turn["decision"]
            elif not current_encounter and active_encounter:
                # 正常关闭 encounters
                closed_encounters = {
                    "encounter_id": active_encounter["encounter_id"],
                    "entered_at": active_encounter["entered_at"],
                    "closed_at": turn["decision"],
                    "duration": turn["decision"] - active_encounter["entered_at"],
                }
                active_encounter = None
            elif not current_encounter and not active_encounter:
                # 无 encounter 活动
                pass
        
        # 检查测试结束时的状态
        if active_encounter:
            findings.append({
                "level": "P0",
                "category": "ENCOUNTER_STILL_ACTIVE",
                "message": f"Encounter {active_encounter['encounter_id']} 在第 {active_encounter['entered_at']} 轮进入，测试结束时仍未退出",
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


class AutoplayRunner:
    """单个测试运行的执行器 - 封装状态和数据采集"""
    
    def __init__(self, save_dir: Path, output_dir: Path):
        self.save_dir = save_dir
        self.output_dir = output_dir
        self.telemetry = TelemetryRecorder()
        self.initial_state = None
        self.final_state = None
        self.events_before_all = []
        self.all_new_events = []
        
    def run(self, turns: int, policy: Policy, seed: int = 42) -> Dict[str, Any]:
        """运行测试并返回结果字典
        
        Returns:
            {
                "status": "success" | "failed" | "timeout",
                "turns_completed": int,
                "total_turns": int,
                "telemetry": TelemetryRecorder,
                "initial_state": dict,
                "final_state": dict,
                "events": list,
            }
        """
        try:
            # 加载游戏状态 (仅第一次)
            state = load_game_state(self.save_dir)
            engine = GameEngine(state)
            
            # 保存初始状态快照
            self.initial_state = self._capture_snapshot(engine)
            
            # 记录起始事件数
            self.events_before_all = engine.state.store.events()
            
            # 生成初始选项
            generate_options_only = False
            pending = engine.state.meta.get("pending_options", {})
            if not pending or not pending.get("options"):
                generate_options_only = True
            
            for decision in range(1, turns + 1):
                # 如果没有待选项，只生成一次
                if generate_options_only:
                    result = resolve_turn(engine, "", None, generate_options_only=True)
                    generate_options_only = False
                
                # 检查是否有错误
                if "error" in result:
                    self.telemetry.add_warning(
                        "P0", 
                        "OPTIONS_GENERATION_FAILED",
                        f"决策 {decision}: {result.get('error', '未知错误')}"
                    )
                    break
                
                visible_options = result.get("visible_options", {})
                option_labels = {k: v.get("label", "") for k, v in visible_options.items()}
                
                # 选择选项 (使用同一个 policy 实例)
                requested = policy.choose(decision, visible_options)
                
                if requested is None:
                    self.telemetry.add_warning(
                        "P1", 
                        "NO_CHOICE_MADE",
                        f"决策 {decision}: 策略无法选择，可用选项：{list(visible_options.keys())}"
                    )
                    break
                
                # 记录执行前状态 (从 SQLite 读取 raw events)
                events_before_run = engine.state.store.events()
                events_count_before = len(events_before_run)
                
                # 记录 before 快照
                before = self._capture_snapshot(engine)
                before["events_count"] = events_count_before
                
                # 获取待执行的 action contract
                pending_opts = engine.state.meta.get("pending_options", {})
                selected_action = {}
                if isinstance(pending_opts, dict) and pending_opts.get("options"):
                    opt = pending_opts["options"].get(requested, {})
                    if isinstance(opt, dict):
                        selected_action = dict(opt.get("action", {}))
                
                # 执行回合
                result = resolve_turn(engine, requested, None)
                
                # 记录 after 快照
                after = self._capture_snapshot(engine)
                
                # 采集新事件 (这才是真实数据源!)
                events_after_run = engine.state.store.events()
                new_events = events_after_run[events_count_before:]
                
                # 提取 action_type 和 time_cost 从原始事件
                action_type = selected_action.get("type", "UNKNOWN")
                time_cost = 0.0
                
                for evt in new_events:
                    if isinstance(evt, dict):
                        data = evt.get("data", {})
                        if isinstance(data, dict):
                            # 从 payload 中提取 time_cost
                            if "time_cost" in data:
                                time_cost = float(data["time_cost"])
                                break
                
                # 记录 telemetry
                self.telemetry.record_turn(
                    turn=engine.state.current_turn,
                    decision=decision,
                    requested_choice=requested,
                    actual_choice=requested,
                    reason_fallback=None,
                    before=before,
                    options_before=option_labels,
                    result={
                        "action_type": action_type,
                        "time_cost": time_cost,
                        "outcome": result.get("resolved", {}).get("resolution", {}).get("outcome", ""),
                    },
                    after=after,
                    events_created=[dict(e) for e in new_events],
                )
                
                # 收集所有事件
                self.all_new_events.extend(new_events)
                
                # 进度输出
                if decision % 10 == 0:
                    print(f"   决策 {decision}/{turns} ✓")
            
            # 保存最终状态快照
            self.final_state = self._capture_snapshot(engine)
            
            return {
                "status": "success",
                "turns_completed": len(self.telemetry.turns),
                "total_turns": turns,
                "telemetry": self.telemetry,
                "initial_state": self.initial_state,
                "final_state": self.final_state,
                "events": self.all_new_events,
                "output_dir": self.output_dir,
            }
        
        except Exception as e:
            import traceback
            
            # 保存失败现场
            failure_dir = self.output_dir / "failure"
            failure_dir.mkdir(parents=True, exist_ok=True)
            
            with open(failure_dir / "traceback.txt", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            
            # 尝试保存崩溃前的状态
            try:
                if 'engine' in locals():
                    failure_dir.joinpath("before_state.json").write_text(
                        json.dumps(self._capture_snapshot(engine), ensure_ascii=False, indent=2)
                    )
                    failure_dir.joinpath("pending_options.json").write_text(
                        json.dumps(engine.state.meta.get("pending_options", {}), ensure_ascii=False, indent=2)
                    )
            except:
                pass
            
            return {
                "status": "failed",
                "error": str(e),
                "output_dir": self.output_dir,
            }
    
    def _capture_snapshot(self, engine: GameEngine) -> Dict[str, Any]:
        """捕获完整的 state 快照"""
        player = engine.state.player
        meta = engine.state.meta
        inventory = engine.state.inventory
        
        # 完整的 snapshot
        return {
            "current_turn": engine.state.current_turn,
            "world_turn": engine.state.world_turn,
            "game_day": meta.get("game_day"),
            "day_elapsed_minutes": meta.get("day_elapsed_minutes"),
            "time_of_day": meta.get("time_of_day"),
            "available_time_minutes": meta.get("available_time_minutes"),
            
            "current_location": meta.get("current_location"),
            "current_encounter_id": meta.get("current_encounter_id"),
            "active_encounters": meta.get("active_encounters", []),
            
            "hp": player.get("hp"),
            "max_hp": player.get("max_hp"),
            "fatigue": player.get("fatigue"),
            "mental": player.get("mental"),
            "hunger": player.get("hunger"),
            
            "level": player.get("level"),
            "exp": player.get("exp"),
            
            "resources": dict(inventory.get("resources", {})),
            
            "event_queue_size": len(meta.get("event_queue", [])),
            "promise_count": len(meta.get("social_state", {}).get("promises", [])),
            
            "peer_action_history_size": len(engine.state.data.get("population_state", {}).get("turn_history", [])),
            "channel_feed_size": len(engine.state.data.get("public_system_state", {}).get("channel_feed", [])),
            
            "total_decisions": meta.get("total_decisions"),
            "total_combats": meta.get("total_combats"),
        }




def main():
    # P1-9: 添加 Python path 初始化以确保模块导入
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
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
    
    try:
        runner = AutoplayRunner(temp_save_dir, output_dir)
        
        # 加载游戏状态 (仅一次)
        state = load_game_state(temp_save_dir)
        engine = GameEngine(state)
        
        # 生成初始选项
        generate_options_only = False
        pending = engine.state.meta.get("pending_options", {})
        if not pending or not pending.get("options"):
            generate_options_only = True
        
        # 创建策略实例 (一次，而不是每轮) - P1-1
        policy = create_policy(args.policy, args.seed)
        
        print(f"🎮 开始模拟 {args.turns} 轮...")
        
        for decision in range(1, args.turns + 1):
            # 如果没有待选项，只生成一次 - P1-4
            if generate_options_only:
                result = resolve_turn(engine, "", None, generate_options_only=True)
                generate_options_only = False
            
            # 检查是否有错误
            if "error" in result or "visible_options" not in result:
                runner.telemetry.add_warning(
                    "P0", 
                    "OPTIONS_GENERATION_FAILED",
                    f"决策 {decision}: {result.get('error', '未知错误')}"
                )
                break
            
            visible_options = result.get("visible_options", {})
            option_labels = {k: v.get("label", "") for k, v in visible_options.items()}
            
            # 选择选项 - P1-2: Aggressive/Builder 需要读取 pending options 的 action
            requested = policy.choose(decision, visible_options, engine.state.meta.get("pending_options", {}))
            
            if requested is None:
                runner.telemetry.add_warning(
                    "P1", 
                    "NO_CHOICE_MADE",
                    f"决策 {decision}: 策略无法选择，可用选项：{list(visible_options.keys())}"
                )
                break
            
            # 记录执行前状态 (从 SQLite 读取 raw events) - P0-1
            events_before_run = engine.state.store.events()
            events_count_before = len(events_before_run)
            
            # 记录 before 快照 - P0-2
            before = runner._capture_snapshot(engine)
            before["events_count"] = events_count_before
            
            # 获取待执行的 action contract
            pending_opts = engine.state.meta.get("pending_options", {})
            selected_action = {}
            if isinstance(pending_opts, dict) and pending_opts.get("options"):
                opt = pending_opts["options"].get(requested, {})
                if isinstance(opt, dict):
                    selected_action = dict(opt.get("action", {}))
            
            # 执行回合
            result = resolve_turn(engine, requested, None)
            
            # 记录 after 快照
            after = runner._capture_snapshot(engine)
            
            # 采集新事件 (这才是真实数据源!) - P0-1
            events_after_run = engine.state.store.events()
            new_events = events_after_run[events_count_before:]
            
            # 提取 action_type 和 time_cost 从原始事件
            action_type = selected_action.get("type", "UNKNOWN")
            time_cost = 0.0
            
            for evt in new_events:
                if isinstance(evt, dict):
                    data = evt.get("data", {})
                    if isinstance(data, dict):
                        if "time_cost" in data:
                            time_cost = float(data["time_cost"])
                            break
            
            # 记录 telemetry
            runner.telemetry.record_turn(
                turn=engine.state.current_turn,
                decision=decision,
                requested_choice=requested,
                actual_choice=requested,
                reason_fallback=None,
                before=before,
                options_before=option_labels,
                result={
                    "action_type": action_type,
                    "time_cost": time_cost,
                    "outcome": result.get("resolved", {}).get("resolution", {}).get("outcome", ""),
                },
                after=after,
                events_created=[dict(e) for e in new_events],
            )
            
            # 收集所有事件
            runner.all_new_events.extend(new_events)
            
            # 进度输出
            if decision % 10 == 0:
                print(f"   决策 {decision}/{args.turns} ✓")
        
        # 保存最终状态快照
        runner.final_state = runner._capture_snapshot(engine)
        
    except Exception as e:
        print(f"❌ 异常：{e}")
        import traceback
        traceback.print_exc()
        
        # P1-8: 增强失败现场保存
        failure_dir = output_dir / "failure"
        failure_dir.mkdir(exist_ok=True)
        
        with open(failure_dir / "traceback.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        
        return
    
    finally:
        # 清理临时文件
        if temp_save_dir.exists():
            shutil.rmtree(temp_save_dir)
    
    # 运行审计
    print(f"🔍 运行自动审计...")
    auditor = AutoAuditor(runner.telemetry)
    findings = auditor.audit()
    
    # 统一统计所有 warning - P0-4
    all_findings = runner.telemetry.warnings + findings
    
    # 添加审计报告
    runner.telemetry.warnings.extend(findings)
    
    # 生成报告
    print(f"📊 生成报告...")
    
    # 计算统计数据
    completed = len(runner.telemetry.turns) == args.turns
    has_p0 = any(f["level"] == "P0" for f in all_findings)
    
    # 确定退出码 - P0-4
    exit_code = 0
    if not completed:
        exit_code = 2  # 未跑完
    elif has_p0:
        exit_code = 2  # 有 P0 问题
    
    # 保存原始数据
    with open(output_dir / "turns.jsonl", "w", encoding="utf-8") as f:
        f.write(runner.telemetry.to_jsonl())
    
    # run.json 包含完整状态信息
    run_data = {
        "summary": runner.telemetry.get_summary(),
        "findings": all_findings,
        "start_time": timestamp,
        "policy": args.policy,
        "turns_requested": args.turns,
        "turns_completed": len(runner.telemetry.turns),
        "completed_normally": completed,
        "has_p0_issues": has_p0,
        "exit_code": exit_code,
    }
    
    with open(output_dir / "run.json", "w", encoding="utf-8") as f:
        json.dump(run_data, f, ensure_ascii=False, indent=2)
    
    # P1-7: 实现 initial/final state snapshots
    with open(output_dir / "initial_state.json", "w", encoding="utf-8") as f:
        json.dump(runner.initial_state, f, ensure_ascii=False, indent=2)
    
    with open(output_dir / "final_state.json", "w", encoding="utf-8") as f:
        json.dump(runner.final_state, f, ensure_ascii=False, indent=2)
    
    with open(output_dir / "events.json", "w", encoding="utf-8") as f:
        json.dump([dict(e) for e in runner.all_new_events], f, ensure_ascii=False, indent=2)
    
    # 生成 Markdown 报告
    report_lines = []
    report_lines.append("# Autoplay Audit Report\n")
    report_lines.append(f"**时间**: {timestamp}\n")
    report_lines.append(f"**策略**: {args.policy}\n")
    report_lines.append(f"**回合数**: {args.turns}\n\n")
    
    # 结果概览
    report_lines.append("## Result\n")
    report_lines.append(f"- 决策完成：{len(runner.telemetry.turns)}/{args.turns}\n")
    report_lines.append(f"- 是否完整跑完：{'是' if completed else '否'}\n")
    report_lines.append(f"- 发现警告：{len(all_findings)}\n")
    
    p0_count = sum(1 for f in all_findings if f["level"] == "P0")
    p1_count = sum(1 for f in all_findings if f["level"] == "P1")
    p2_count = sum(1 for f in all_findings if f["level"] == "P2")
    
    report_lines.append(f"- P0 问题：{p0_count}\n")
    report_lines.append(f"- P1 问题：{p1_count}\n")
    report_lines.append(f"- P2 问题：{p2_count}\n\n")
    
    # 机制覆盖
    report_lines.append("## Coverage\n")
    mechanism_counts: Dict[str, int] = {}
    for turn in runner.telemetry.turns:
        mech = turn["result"].get("action_type", "UNKNOWN")
        mechanism_counts[mech] = mechanism_counts.get(mech, 0) + 1
    
    for mech, count in sorted(mechanism_counts.items()):
        marker = " ⚠" if count == 0 else ""
        report_lines.append(f"- {mech}: {count}{marker}\n")
    report_lines.append("\n")
    
    # 问题列表
    if all_findings:
        report_lines.append("## Findings\n\n")
        
        for finding in all_findings:
            level = finding["level"]
            category = finding["category"]
            message = finding["message"]
            
            icon = "🔴" if level == "P0" else "🟠" if level == "P1" else "🟡"
            report_lines.append(f"### {icon} [{level}] {category}\n")
            report_lines.append(f"{message}\n\n")
    
    # 最终状态
    if runner.final_state:
        report_lines.append("## Final State\n")
        report_lines.append(f"- Turn: {runner.final_state.get('current_turn')}\n")
        report_lines.append(f"- World Turn: {runner.final_state.get('world_turn')}\n")
        report_lines.append(f"- Day: {runner.final_state.get('game_day')}\n")
        report_lines.append(f"- Location: {runner.final_state.get('current_location')}\n")
        report_lines.append(f"- HP: {runner.final_state.get('hp')}/...\n")
        report_lines.append(f"- Mental: {runner.final_state.get('mental')}\n\n")
    
    report_text = "\n".join(report_lines)
    
    with open(output_dir / "report.md", "w", encoding="utf-8") as f:
        f.write(report_text)
    
    # 打印简要摘要
    print(f"\n✅ 完成！输出目录：{output_dir.absolute()}\n")
    print("== 报告摘要 ==")
    print(f"完成：{len(runner.telemetry.turns)}/{args.turns}")
    print(f"P0 问题：{p0_count}")
    print(f"P1 问题：{p1_count}")
    print(f"P2 问题：{p2_count}")
    
    if p0_count > 0:
        print(f"\n⚠️  发现 {p0_count} 个 P0 级问题，请详细检查！")
    
    # 设置全局 exit code (供 Suite 读取) - P0-4
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
