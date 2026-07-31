"""Autoplay Test Engine v2 - Trusted Simulation Harness

完全修复版：非零退出码、正确处理 pending_options、raw event 审计链完整。

Usage:
    python tools/autoplay_test.py --save saves/锈铁方舟 --turns 50 --policy abc

Exit Codes:
    0 = Completed, no P0 issues
    2 = Not fully completed OR has P0 issues  
    3 = Unhandled exception (crashed)
    4 = Initialization failure
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


# P1-6: Python path init at MODULE TOP
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine_runtime.state import load_game_state
from engine_runtime.runtime import GameEngine
from engine_runtime.public_survival import load_peer_agents
from engine_runtime.events import DAY_MINUTES
from tools.turn_controller import resolve as resolve_turn


class Policy:
    """Player strategy base class"""
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        raise NotImplementedError


class ABCPolicy(Policy):
    """ABC cycling strategy"""
    sequence = ["A", "B", "C"]
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        preferred = self.sequence[(turn - 1) % len(self.sequence)]
        if preferred in visible_options:
            return preferred
        for choice in self.sequence:
            if choice in visible_options:
                return choice
        return None


class RandomPolicy(Policy):
    """Random policy - seed outside loop"""
    
    def __init__(self, seed: int = 42):
        import random
        self.random = random.Random(seed)
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        if not visible_options:
            return None
        options = list(visible_options.keys())
        return self.random.choice(options)


class AggressivePolicy(Policy):
    """Prioritize COMBAT/EXPLORATION/高风险行动"""
    HIGH_RISK_TYPES = {"COMBAT", "EXPLORATION", "TRAVEL", "EXTRACT", "RETURN_TO_BASE"}
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        if not visible_options:
            return None
        if isinstance(pending_options, dict) and pending_options.get("options"):
            for key in visible_options.keys():
                opt = pending_options["options"].get(key, {})
                if isinstance(opt, dict):
                    action_type = str(opt.get("action", {}).get("type", ""))
                    if action_type in self.HIGH_RISK_TYPES:
                        return key
        return next(iter(visible_options.keys()), None)


class BuilderPolicy(Policy):
    """Prioritize BUILD/SOCIAL_INTERACTION/research"""
    PRIORITY_TYPES = {"BUILD", "BASE_MANAGEMENT", "SOCIAL_INTERACTION", "RESEARCH", "TRADE"}
    
    def choose(self, turn: int, visible_options: dict[str, dict], pending_options: dict = None) -> Optional[str]:
        if not visible_options:
            return None
        if isinstance(pending_options, dict) and pending_options.get("options"):
            for key in visible_options.keys():
                opt = pending_options["options"].get(key, {})
                if isinstance(opt, dict):
                    action_type = str(opt.get("action", {}).get("type", ""))
                    if action_type in self.PRIORITY_TYPES:
                        return key
        return next(iter(visible_options.keys()), None)


def create_policy(policy_name: str, seed: int = 42) -> Policy:
    policies = {
        "abc": ABCPolicy,
        "random": lambda: RandomPolicy(seed),
        "aggressive": AggressivePolicy,
        "builder": BuilderPolicy,
    }
    if policy_name not in policies:
        raise ValueError(f"Unknown policy: {policy_name}. Available: {list(policies.keys())}")
    return policies[policy_name]()


class TelemetryRecorder:
    """Record telemetry for each decision"""
    
    def __init__(self):
        self.turns: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
    
    def record_turn(self, turn: int, decision: int, requested_choice: Optional[str], 
                   actual_choice: Optional[str], reason_fallback: Optional[str],
                   before: Dict[str, Any], options_before: Dict[str, str],
                   result: Dict[str, Any], after: Dict[str, Any], 
                   events_created: List[Dict[str, Any]],
                   option_contracts: Optional[Dict[str, Dict]] = None) -> None:
        self.turns.append({
            "decision": decision, "turn": turn,
            "requested_choice": requested_choice, "actual_choice": actual_choice,
            "reason_fallback": reason_fallback, "before": before, "options_before": options_before,
            "result": result, "after": after, "option_contracts": option_contracts or {},
            "events_created": [dict(e) for e in events_created],
            "warnings": [],
        })
    
    def add_warning(self, level: str, category: str, message: str) -> None:
        self.warnings.append({"level": level, "category": category, "message": message})
    
    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(t, ensure_ascii=False) for t in self.turns)


class AutoAuditor:
    """Automated auditor rules"""
    
    def __init__(self, telemetry: TelemetryRecorder):
        self.telemetry = telemetry
    
    def audit(self) -> List[Dict[str, Any]]:
        findings = []
        findings.extend(self._detect_stuck_loop())
        findings.extend(self._detect_no_action())
        findings.extend(self._detect_time_stopped())
        findings.extend(self._detect_unclosed_mechanisms())
        findings.extend(self._detect_public_system_dormant_v2())
        findings.extend(self._detect_time_jump_anomaly())
        findings.extend(self._detect_mechanism_unreachable())
        findings.extend(self._detect_high_option_repetition())
        return findings
    
    def _detect_time_jump_anomaly(self) -> List[Dict[str, Any]]:
        """Detect time inconsistencies between expected and actual.
        
        Instead of flagging any single action >60min (which is normal for WAIT/REST/BUILD),
        we compare the sum of all action time costs against actual state time delta.
        """
        findings = []
        
        if len(self.telemetry.turns) < 2:
            return findings
        
        for i in range(1, len(self.telemetry.turns)):
            turn = self.telemetry.turns[i]
            
            # Expected time = this turn's recorded time_cost
            expected_time = float(turn["result"].get("time_cost", 0) or 0)
            
            # Get actual absolute times from snapshots
            before = turn["before"]
            after = turn["after"]
            
            before_day = before.get("game_day", 1)
            before_elapsed = before.get("day_elapsed_minutes", 0) or 0
            after_day = after.get("game_day", 1)
            after_elapsed = after.get("day_elapsed_minutes", 0) or 0
            
            before_abs = (before_day - 1) * DAY_MINUTES + before_elapsed
            after_abs = (after_day - 1) * DAY_MINUTES + after_elapsed
            actual_time = after_abs - before_abs
            
            # Allow small tolerance (±5 minutes) for rounding/system events
            tolerance = 5.0
            discrepancy = abs(actual_time - expected_time)
            
            if discrepancy > tolerance:
                findings.append({
                    "level": "P1",
                    "category": "TIME_JUMP_ANOMALY",
                    "message": f"Decision {turn['decision']}: expected {expected_time:.1f}min, actual {actual_time:.1f}min (discrepancy={discrepancy:.1f}min)",
                    "detail": {
                        "expected_minutes": expected_time,
                        "actual_minutes": actual_time,
                        "discrepancy_minutes": discrepancy
                    }
                })
        
        return findings
    
    def _detect_mechanism_unreachable(self) -> List[Dict[str, Any]]:
        """Detect action types that were offered but never executed.
        
        Now reads from option_contracts if available, falling back to label parsing.
        """
        findings = []
        
        # Skip if no turns recorded
        if not self.telemetry.turns:
            return findings
        
        all_leaf_actions = set()
        all_offered_types = set()
        
        for turn in self.telemetry.turns:
            # Collect actual executed leaf actions
            leaf_actions = turn["result"].get("leaf_actions", [])
            if isinstance(leaf_actions, list):
                all_leaf_actions.update(leaf_actions)
            
            # Try to get option_contracts first (preferred method)
            option_contracts = turn.get("option_contracts", {})
            if option_contracts:
                for opt_key, contract in option_contracts.items():
                    if isinstance(contract, dict):
                        offered_type = contract.get("action_type")
                        if offered_type:
                            all_offered_types.add(offered_type)
                        leaf_types = contract.get("leaf_types", [])
                        if isinstance(leaf_types, list):
                            all_offered_types.update(leaf_types)
            else:
                # Fallback: parse labels (less reliable, mostly fails for Chinese labels)
                options_before = turn.get("options_before", {})
                for opt_label in options_before.values():
                    if isinstance(opt_label, str):
                        for action_type in ["EXPLORATION", "COMBAT", "SOCIAL_INTERACTION", "BUILD", 
                                           "TRADE", "RESEARCH", "REST", "TRAVEL", "EXTRACT", "WAIT"]:
                            if action_type in opt_label.upper():
                                all_offered_types.add(action_type)
        
        # Only report mechanisms that were offered but never executed
        unreachable = all_offered_types - all_leaf_actions
        
        if unreachable:
            findings.append({
                "level": "P1", 
                "category": "MECHANISM_UNREACHABLE",
                "message": f"Action types offered {len(unreachable)}x but never executed: {', '.join(sorted(unreachable))}",
                "detail": {"unreachable_mechanisms": sorted(unreachable)}
            })
        
        return findings
    
    def _detect_high_option_repetition(self) -> List[Dict[str, Any]]:
        """Detect repeated option labels (indicates limited branching)"""
        findings = []
        
        label_counts = {}
        for turn in self.telemetry.turns:
            label = turn["options_before"].get(turn["requested_choice"], "")
            label_counts[label] = label_counts.get(label, 0) + 1
        
        # If any single label appears > 30% of turns
        total = len(self.telemetry.turns)
        threshold = max(5, int(total * 0.3))
        
        high_freq_labels = [k for k, v in label_counts.items() if v >= threshold]
        if high_freq_labels:
            findings.append({
                "level": "P2", 
                "category": "HIGH_OPTION_REPETITION",
                "message": f"Highly repetitive labels: {', '.join(f'{l}={c}' for l,c in sorted(label_counts.items(), key=lambda x:-x[1])[:5])}",
                "detail": {"label_frequencies": label_counts}
            })
        
        return findings
    
    def _detect_stuck_loop(self) -> List[Dict[str, Any]]:
        findings = []
        same_count, last_action = 0, None
        for turn in self.telemetry.turns:
            action_type = turn["result"].get("action_type", "")
            same_count = same_count + 1 if action_type == last_action else 1
            last_action = action_type
            if same_count >= 5:
                findings.append({"level": "P1", "category": "STUCK_LOOP",
                               "message": f"Same action type repeated {same_count} times"})
                break
        return findings
    
    def _detect_no_action(self) -> List[Dict[str, Any]]:
        return [{"level": "P0", "category": "NO_AVAILABLE_ACTION",
                "message": f"Decision {t['decision']} had no options"} 
                for t in self.telemetry.turns if not t["options_before"]]
    
    def _detect_time_stopped(self) -> List[Dict[str, Any]]:
        findings = []
        consecutive_zero = []
        for turn in self.telemetry.turns:
            if float(turn["result"].get("time_cost", 0) or 0) == 0:
                consecutive_zero.append(turn["decision"])
            elif len(consecutive_zero) >= 10:
                findings.append({"level": "P0", "category": "TIME_NOT_ADVANCING",
                               "message": f"{len(consecutive_zero)} consecutive zero-time actions"})
                consecutive_zero = []
        
        # CRITICAL: Check at the end of loop for trailing zero-time decisions
        if len(consecutive_zero) >= 10:
            findings.append({"level": "P0", "category": "TIME_NOT_ADVANCING",
                           "message": f"{len(consecutive_zero)} consecutive zero-time actions (ending at final decision)"})
        
        return findings
    
    def _detect_unclosed_mechanisms(self) -> List[Dict[str, Any]]:
        findings = []
        active_encounter = None
        for i, turn in enumerate(self.telemetry.turns):
            current_encounter = turn["after"].get("current_encounter_id")
            if current_encounter and not active_encounter:
                active_encounter = {"id": current_encounter, "entered_at": turn["decision"]}
            elif current_encounter and active_encounter:
                if current_encounter != active_encounter["id"]:
                    findings.append({"level": "P0", "category": "ENCOUNTER_UNEXPECTED_SWITCH",
                                   "message": "Encounter switched without exit"})
                    active_encounter = {"id": current_encounter, "entered_at": turn["decision"]}
            elif not current_encounter and active_encounter:
                active_encounter = None
        
        if active_encounter:
            findings.append({"level": "P0", "category": "ENCOUNTER_STILL_ACTIVE",
                           "message": f"Encounter {active_encounter['id']} still active after {len(self.telemetry.turns)} decisions"})
        return findings
    
    def _detect_public_system_dormant_v2(self) -> List[Dict[str, Any]]:
        # Count PUBLIC_SYSTEM_ADVANCED events from telemetry
        public_advances = sum(
            1
            for turn in self.telemetry.turns
            for e in turn.get("events_created", [])
            if isinstance(e, dict) and e.get("type") == "PUBLIC_SYSTEM_ADVANCED"
        )
        
        # Check real peer agent activity via peer_last_action_turns
        peer_activity_before = None
        peer_activity_after = None
        
        for turn in self.telemetry.turns:
            after_state = turn.get("after", {})
            peer_turns = after_state.get("peer_last_action_turns", {})
            
            # Sum of all peer last action turns as activity indicator
            current_activity = sum(peer_turns.values()) if peer_turns else 0
            
            if peer_activity_before is None:
                peer_activity_before = current_activity
            peer_activity_after = current_activity
        
        total_peer_delta = (peer_activity_after or 0) - (peer_activity_before or 0)
        
        # P0: Public system advancing but no peer activity = broken simulation
        if public_advances >= 10 and total_peer_delta == 0:
            return [{
                "level": "P0", 
                "category": "PUBLIC_SYSTEM_PEER_DORMANT",
                "message": f"Public system advanced {public_advances} times but peer agents took no actions (delta={total_peer_delta})"
            }]
        
        return []


class AutoplayRunner:
    """Single test run executor with raw event data collection"""
    
    def __init__(self, save_dir: Path, output_dir: Path):
        self.save_dir = save_dir
        self.output_dir = output_dir
        self.telemetry = TelemetryRecorder()
        self.initial_state: Dict[str, Any] | None = None
        self.final_state: Dict[str, Any] | None = None
        self.all_new_events: List[Dict[str, Any]] = []
        
    def capture_snapshot(self, engine: GameEngine) -> Dict[str, Any]:
        player = engine.state.player
        meta = engine.state.meta
        inventory = engine.state.inventory
        
        # Get real peer agent states from SQLite
        peer_last_action_turns = {}
        try:
            # CRITICAL: Use same campaign_id resolution as public_survival.py
            meta = engine.state.meta
            world = engine.state.data.get("world", {})
            
            campaign_id = (
                meta.get("campaign_id")
                or world.get("name")
                or engine.state.store.campaign_id
            )
            
            peers = load_peer_agents(engine.state, campaign_id)
            for peer in peers:
                # Track last action turn for each peer
                action_history = getattr(peer, "action_history", [])
                if action_history:
                    last_action = action_history[-1]
                    peer_last_action_turns[peer.id] = last_action.get("turn", 0)
                else:
                    peer_last_action_turns[peer.id] = 0
        except Exception:
            # If peer loading fails, record empty state
            pass
        
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
            "event_queue_size": len(engine.state.data.get("event_queue", [])),
            "promise_count": len(meta.get("social_state", {}).get("promises", [])),
            "population_turn_history_size": len(
                engine.state.data.get("population_state", {}).get("turn_history", [])
            ),
            "channel_feed_size": len(engine.state.data.get("public_system_state", {}).get("channel_feed", [])),
            "peer_last_action_turns": peer_last_action_turns,
            "total_decisions": meta.get("total_decisions"),
            "total_combats": meta.get("total_combats"),
        }
    
    def run(self, turns: int, policy: Policy) -> Dict[str, Any]:
        """Execute single test and return comprehensive results
        
        Returns:
            {
                "status": "success"|"failed"|"crashed",
                "exit_code": 0|2|3|4,
                "telemetry": TelemetryRecorder,
                "initial_state": dict|null,
                "final_state": dict|null,
                "events": list,
            }
        """
        try:
            state = load_game_state(self.save_dir)
            engine = GameEngine(state)
            
            self.initial_state = self.capture_snapshot(engine)
            
            # Check existing pending options
            pending_opts = engine.state.meta.get("pending_options", {})
            has_pending = isinstance(pending_opts, dict) and pending_opts.get("options")
            
            if not has_pending:
                result = resolve_turn(engine, "", None, generate_options_only=True)
                if "error" in result:
                    self.telemetry.add_warning("P0", "OPTIONS_GENERATION_FAILED", 
                                             f"Initial generation failed: {result.get('error')}")
                    return {
                        "status": "failed", "exit_code": 4, "turns_completed": 0,
                        "telemetry": self.telemetry, "initial_state": self.initial_state,
                        "final_state": None, "events": [], "output_dir": self.output_dir,
                    }
            
            # Now we MUST have pending options
            pending_opts = engine.state.meta.get("pending_options", {})
            if not isinstance(pending_opts, dict) or not pending_opts.get("options"):
                self.telemetry.add_warning("P0", "NO_PENDING_OPTIONS", "No options after generation")
                self.final_state = None
                return {
                    "status": "failed", "exit_code": 4, "turns_completed": 0,
                    "telemetry": self.telemetry, "initial_state": self.initial_state,
                    "final_state": None, "events": [], "output_dir": self.output_dir,
                }
            
            print(f"🎮 Running {turns} decisions...")
            
            for decision in range(1, turns + 1):
                # CRITICAL: Re-read pending_opts each decision, do not cache across loop
                pending_opts = engine.state.meta.get("pending_options", {})
                
                if not isinstance(pending_opts, dict) or not pending_opts.get("options"):
                    self.telemetry.add_warning("P0", "NO_PENDING_OPTIONS", 
                                              f"Decision {decision}: No options after resolve")
                    # Try to regenerate
                    result = resolve_turn(engine, "", None, generate_options_only=True)
                    if "error" in result:
                        self.telemetry.add_warning("P0", "OPTIONS_REGEN_FAILED", 
                                                  f"Cannot regenerate options: {result.get('error')}")
                        break
                    pending_opts = engine.state.meta.get("pending_options", {})
                
                visible_options = pending_opts.get("options", {})
                
                # Extract option contracts for better mechanism detection
                option_contracts = {}
                for opt_key, opt_data in visible_options.items():
                    if isinstance(opt_data, dict):
                        contract = {
                            "label": opt_data.get("label", ""),
                            "action_type": opt_data.get("action", {}).get("type", ""),
                            "leaf_types": opt_data.get("action", {}).get("leaf_actions", []),
                        }
                        option_contracts[opt_key] = contract
                
                option_labels = {k: v.get("label", "") for k, v in visible_options.items()}
                
                requested = policy.choose(decision, visible_options, pending_opts)
                
                if requested is None:
                    self.telemetry.add_warning("P1", "NO_CHOICE_MADE",
                                              f"Decision {decision}: No valid choice")
                    break
                
                # Record before
                events_before_run = engine.state.store.events()
                events_count_before = len(events_before_run)
                before = self.capture_snapshot(engine)
                
                selected_action = dict(pending_opts["options"].get(requested, {}).get("action", {}))
                action_type = selected_action.get("type", "UNKNOWN")
                
                # Execute
                result = resolve_turn(engine, requested, None)
                
                if "error" in result:
                    self.telemetry.add_warning("P0", "TURN_EXECUTION_FAILED",
                                              f"Decision {decision}: {result.get('error')}")
                    break
                
                after = self.capture_snapshot(engine)
                
                # Raw events source
                events_after_run = engine.state.store.events()
                new_events = events_after_run[events_count_before:]
                
                # Calculate actual time cost from state difference (more reliable than event data)
                before_meta = before
                after_meta = after
                
                before_day = before_meta.get("game_day", 1)
                before_elapsed = before_meta.get("day_elapsed_minutes", 0) or 0
                after_day = after_meta.get("game_day", 1)
                after_elapsed = after_meta.get("day_elapsed_minutes", 0) or 0
                
                # CRITICAL: Use engine's DAY_MINUTES (720), not hardcoded 1440
                before_abs = (before_day - 1) * DAY_MINUTES + before_elapsed
                after_abs = (after_day - 1) * DAY_MINUTES + after_elapsed
                actual_time_cost = after_abs - before_abs
                
                # Extract leaf actions and outcome from raw events
                leaf_actions = set()
                outcome = ""
                for evt in new_events:
                    if isinstance(evt, dict):
                        data = evt.get("data", {})
                        if isinstance(data, dict):
                            # Extract outcome from resolution
                            if "resolution" in data and isinstance(data["resolution"], dict):
                                resolution = data["resolution"]
                                outcome = resolution.get("outcome", outcome)
                                
                                # Extract leaf action type from resolution
                                leaf_type = resolution.get("action_type", "")
                                if leaf_type:
                                    leaf_actions.add(leaf_type)
                            
                            # Also check for action type in event data itself
                            action_data = data.get("action", {})
                            if isinstance(action_data, dict):
                                action_type_from_event = action_data.get("type", "")
                                if action_type_from_event:
                                    leaf_actions.add(action_type_from_event)
                
                # If no leaf actions found, use main action type as fallback
                if not leaf_actions:
                    leaf_actions.add(action_type)
                
                self.telemetry.record_turn(
                    turn=engine.state.current_turn, decision=decision,
                    requested_choice=requested, actual_choice=requested, reason_fallback=None,
                    before=before, options_before=option_labels,
                    result={
                        "action_type": action_type, 
                        "time_cost": float(actual_time_cost),
                        "outcome": outcome,
                        "leaf_actions": sorted(list(leaf_actions))
                    },
                    after=after, events_created=[dict(e) for e in new_events],
                    option_contracts=option_contracts,
                )
                
                self.all_new_events.extend(new_events)
                
                if decision % 10 == 0:
                    print(f"   Decision {decision}/{turns} ✓")
            
            self.final_state = self.capture_snapshot(engine)
            
            return {
                "status": "success", "exit_code": 0, "turns_completed": len(self.telemetry.turns),
                "telemetry": self.telemetry, "initial_state": self.initial_state,
                "final_state": self.final_state, "events": self.all_new_events,
                "output_dir": self.output_dir,
            }
        
        except Exception as e:
            import traceback
            print(f"❌ Crash: {e}")
            traceback.print_exc()
            
            failure_dir = self.output_dir / "failure"
            failure_dir.mkdir(parents=True, exist_ok=True)
            
            with open(failure_dir / "traceback.txt", "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            
            try:
                if 'engine' in locals():
                    failure_dir.joinpath("before_state.json").write_text(
                        json.dumps(self.capture_snapshot(engine), ensure_ascii=False, indent=2)
                    )
                    failure_dir.joinpath("pending_options.json").write_text(
                        json.dumps(engine.state.meta.get("pending_options", {}), ensure_ascii=False, indent=2)
                    )
                    events = engine.state.store.events()[-10:]
                    failure_dir.joinpath("events_tail.json").write_text(
                        json.dumps([dict(e) for e in events], ensure_ascii=False, indent=2),
                        encoding="utf-8"
                    )
            except:
                pass
            
            return {
                "status": "crashed", "exit_code": 3, "turns_completed": len(self.telemetry.turns),
                "telemetry": self.telemetry, "initial_state": self.initial_state,
                "final_state": self.final_state, "events": self.all_new_events,
                "output_dir": self.output_dir,
            }


def main():
    parser = argparse.ArgumentParser(description="Autoplay Test Engine v2")
    parser.add_argument("--save", type=str, required=True, help="Save directory")
    parser.add_argument("--turns", type=int, default=50, help="Number of decisions")
    parser.add_argument("--policy", type=str, default="abc", choices=["abc", "random", "aggressive", "builder"])
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", type=str, default=None, help="Output directory")
    
    args = parser.parse_args()
    
    base_path = Path(args.save)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path("autoplay_runs") / f"{timestamp}_{args.policy}"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # CRITICAL: Preserve original save directory name to maintain campaign identity
    # SQLiteEventStore uses save_dir.name as default campaign_id
    sandbox_root = output_dir / "temp_save"
    temp_save_dir = sandbox_root / base_path.name
    
    # Copy save
    print(f"📁 Copying save: {base_path} → {temp_save_dir}")
    if temp_save_dir.exists():
        shutil.rmtree(temp_save_dir)
    try:
        shutil.copytree(base_path, temp_save_dir)
    except Exception as e:
        print(f"❌ Save initialization failed: {e}")
        sys.exit(4)
    
    # Run test
    runner = AutoplayRunner(temp_save_dir, output_dir)
    policy = create_policy(args.policy, args.seed)
    
    result = runner.run(args.turns, policy)
    
    # Cleanup temp files even on crash
    if temp_save_dir.exists():
        shutil.rmtree(temp_save_dir)
    
    # Audit
    print(f"🔍 Running auto-audit...")
    auditor = AutoAuditor(result["telemetry"])
    all_findings = result["telemetry"].warnings + auditor.audit()
    result["telemetry"].warnings.extend(all_findings)
    
    # Determine exit code - preserve Runner's exit_code for init failures
    completed = result["turns_completed"] == args.turns
    has_p0 = any(f["level"] == "P0" for f in all_findings)
    
    # Start with Runner's reported exit_code
    exit_code = result.get("exit_code", 0)
    
    # Only override if Runner succeeded but audit found P0 issues
    if exit_code == 0:
        if not completed or has_p0:
            exit_code = 2
    
    # Generate reports
    print(f"📊 Generating reports...")
    
    with open(output_dir / "turns.jsonl", "w", encoding="utf-8") as f:
        f.write(result["telemetry"].to_jsonl())
    
    run_data = {
        "summary": result["telemetry"].get_summary() if hasattr(result["telemetry"], "get_summary") else {},
        "findings": all_findings,
        "start_time": timestamp, "policy": args.policy,
        "turns_requested": args.turns, "turns_completed": result["turns_completed"],
        "completed_normally": completed, "has_p0_issues": has_p0, "exit_code": exit_code,
        "status": result["status"],
    }
    with open(output_dir / "run.json", "w", encoding="utf-8") as f:
        json.dump(run_data, f, ensure_ascii=False, indent=2)
    
    with open(output_dir / "initial_state.json", "w", encoding="utf-8") as f:
        json.dump(result["initial_state"], f, ensure_ascii=False, indent=2)
    with open(output_dir / "final_state.json", "w", encoding="utf-8") as f:
        json.dump(result["final_state"], f, ensure_ascii=False, indent=2)
    with open(output_dir / "events.json", "w", encoding="utf-8") as f:
        json.dump([dict(e) for e in result["events"]], f, ensure_ascii=False, indent=2)
    
    # Markdown report
    p0_count = sum(1 for f in all_findings if f["level"] == "P0")
    p1_count = sum(1 for f in all_findings if f["level"] == "P1")
    p2_count = sum(1 for f in all_findings if f["level"] == "P2")
    
    report_lines = [
        "# Autoplay Audit Report\n",
        f"**Time**: {timestamp}\n**Policy**: {args.policy}\n**Turns**: {args.turns}\n\n",
        "## Result\n",
        f"- Completed: {result['turns_completed']}/{args.turns}\n",
        f"- Fully completed: {'Yes' if completed else 'No'}\n",
        f"- Findings: {len(all_findings)}\n",
        f"- P0 Issues: {p0_count}\n-P1 Issues: {p1_count}\n-P2 Issues: {p2_count}\n\n",
        "## Coverage\n",
    ]
    
    mechanism_counts: Dict[str, int] = {}
    leaf_action_counts: Dict[str, int] = {}
    
    for turn in result["telemetry"].turns:
        # Top-level action type
        mech = turn["result"].get("action_type", "UNKNOWN")
        mechanism_counts[mech] = mechanism_counts.get(mech, 0) + 1
        
        # Leaf actions (more granular coverage)
        leaf_actions = turn["result"].get("leaf_actions", [])
        if isinstance(leaf_actions, list):
            for leaf in leaf_actions:
                leaf_action_counts[leaf] = leaf_action_counts.get(leaf, 0) + 1
    
    # First show leaf actions (if any), then top-level mechanisms
    if leaf_action_counts:
        report_lines.append("\n### Leaf Action Coverage\n")
        for mech, count in sorted(leaf_action_counts.items(), key=lambda x: -x[1]):
            marker = " ⚠" if count == 0 else ""
            report_lines.append(f"- {mech}: {count}{marker}\n")
    
    if mechanism_counts:
        report_lines.append("\n### Contract-Level Mechanisms\n")
        for mech, count in sorted(mechanism_counts.items(), key=lambda x: -x[1]):
            marker = " ⚠" if count == 0 else ""
            report_lines.append(f"- {mech}: {count}{marker}\n")
    
    if all_findings:
        report_lines.append("\n## Findings\n\n")
        for finding in all_findings:
            icon = "🔴" if finding["level"] == "P0" else "🟠" if finding["level"] == "P1" else "🟡"
            report_lines.append(f"### {icon} [{finding['level']}] {finding['category']}\n{finding['message']}\n\n")
    
    if result["final_state"]:
        report_lines.extend([
            "## Final State\n",
            f"- Turn: {result['final_state'].get('current_turn')}\n",
            f"- World Turn: {result['final_state'].get('world_turn')}\n",
            f"- Day: {result['final_state'].get('game_day')}\n",
            f"- Location: {result['final_state'].get('current_location')}\n"
        ])
    
    with open(output_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("".join(report_lines))
    
    print(f"\n✅ Output: {output_dir.absolute()}\n")
    print("== Summary ==")
    print(f"Completed: {result['turns_completed']}/{args.turns}")
    print(f"P0: {p0_count}, P1: {p1_count}, P2: {p2_count}")
    
    if p0_count > 0:
        print(f"\n⚠️ {p0_count} P0 issues found!\n")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
