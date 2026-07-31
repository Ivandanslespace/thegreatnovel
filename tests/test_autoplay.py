"""Unit tests for Autoplay Test Engine v2

Tests for AutoAuditor and AutoplayRunner to catch critical bugs early.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.autoplay_test import (
    AutoAuditor,
    TelemetryRecorder,
    ABCPolicy,
    RandomPolicy,
    AggressivePolicy,
    BuilderPolicy,
    create_policy,
)


class TestTelemetryRecorder(unittest.TestCase):
    """Test TelemetryRecorder basic functionality"""
    
    def test_empty_recorder(self):
        """Empty recorder should have no turns or warnings"""
        recorder = TelemetryRecorder()
        self.assertEqual(len(recorder.turns), 0)
        self.assertEqual(len(recorder.warnings), 0)
    
    def test_record_turn(self):
        """Record a single turn and verify structure"""
        recorder = TelemetryRecorder()
        
        recorder.record_turn(
            turn=1, decision=1,
            requested_choice="A", actual_choice="A",
            reason_fallback=None,
            before={"hp": 100},
            options_before={"A": "Attack", "B": "Defend"},
            result={"action_type": "COMBAT", "time_cost": 30.0, "outcome": "success"},
            after={"hp": 90},
            events_created=[{"type": "ACTION_RESOLVED", "data": {}}],
        )
        
        self.assertEqual(len(recorder.turns), 1)
        turn = recorder.turns[0]
        self.assertEqual(turn["decision"], 1)
        self.assertEqual(turn["requested_choice"], "A")
        self.assertEqual(turn["result"]["action_type"], "COMBAT")
        self.assertEqual(turn["result"]["time_cost"], 30.0)
    
    def test_add_warning(self):
        """Add warning and verify structure"""
        recorder = TelemetryRecorder()
        recorder.add_warning("P0", "TEST_WARNING", "Test message")
        
        self.assertEqual(len(recorder.warnings), 1)
        warning = recorder.warnings[0]
        self.assertEqual(warning["level"], "P0")
        self.assertEqual(warning["category"], "TEST_WARNING")
    
    def test_to_jsonl(self):
        """Convert turns to JSONL format"""
        recorder = TelemetryRecorder()
        recorder.record_turn(
            turn=1, decision=1,
            requested_choice="A", actual_choice="A",
            reason_fallback=None,
            before={}, options_before={},
            result={"action_type": "TEST", "time_cost": 0},
            after={}, events_created=[],
        )
        
        jsonl = recorder.to_jsonl()
        self.assertIsInstance(jsonl, str)
        self.assertIn("TEST", jsonl)


class TestAutoAuditor(unittest.TestCase):
    """Test AutoAuditor detection rules"""
    
    def test_auditor_initialization(self):
        """Auditor should initialize with telemetry recorder"""
        telemetry = TelemetryRecorder()
        auditor = AutoAuditor(telemetry)
        self.assertIs(auditor.telemetry, telemetry)
    
    def test_empty_audit(self):
        """Empty telemetry should produce no findings"""
        telemetry = TelemetryRecorder()
        auditor = AutoAuditor(telemetry)
        findings = auditor.audit()
        
        self.assertIsInstance(findings, list)
        self.assertEqual(len(findings), 0)
    
    def test_detect_no_action(self):
        """Detect when no options are available"""
        telemetry = TelemetryRecorder()
        telemetry.record_turn(
            turn=1, decision=1,
            requested_choice=None, actual_choice=None,
            reason_fallback=None,
            before={}, options_before={},  # Empty options
            result={"action_type": "NONE", "time_cost": 0},
            after={}, events_created=[],
        )
        
        auditor = AutoAuditor(telemetry)
        findings = auditor.audit()
        
        no_action_findings = [f for f in findings if f["category"] == "NO_AVAILABLE_ACTION"]
        self.assertGreater(len(no_action_findings), 0)
        self.assertEqual(no_action_findings[0]["level"], "P0")
    
    def test_detect_stuck_loop(self):
        """Detect repeated same action type"""
        telemetry = TelemetryRecorder()
        
        # Record 5 identical actions
        for i in range(5):
            telemetry.record_turn(
                turn=1, decision=i+1,
                requested_choice="A", actual_choice="A",
                reason_fallback=None,
                before={}, options_before={"A": "Test"},
                result={"action_type": "COMBAT", "time_cost": 30},
                after={}, events_created=[],
            )
        
        auditor = AutoAuditor(telemetry)
        findings = auditor.audit()
        
        stuck_findings = [f for f in findings if f["category"] == "STUCK_LOOP"]
        self.assertGreater(len(stuck_findings), 0)
    
    def test_detect_time_not_advancing(self):
        """Detect consecutive zero-time actions"""
        telemetry = TelemetryRecorder()
        
        # Record 10 zero-time actions
        for i in range(10):
            telemetry.record_turn(
                turn=1, decision=i+1,
                requested_choice="A", actual_choice="A",
                reason_fallback=None,
                before={}, options_before={"A": "Test"},
                result={"action_type": "TEST", "time_cost": 0},
                after={}, events_created=[],
            )
        
        auditor = AutoAuditor(telemetry)
        findings = auditor.audit()
        
        time_findings = [f for f in findings if f["category"] == "TIME_NOT_ADVANCING"]
        self.assertGreater(len(time_findings), 0)
        self.assertEqual(time_findings[0]["level"], "P0")
    
    def test_detect_public_system_dormant(self):
        """Detect public system advancing but no peer activity"""
        telemetry = TelemetryRecorder()
        
        # Simulate public system advancing but no peer actions
        for i in range(15):
            telemetry.record_turn(
                turn=1, decision=i+1,
                requested_choice="A", actual_choice="A",
                reason_fallback=None,
                before={"peer_action_history_size": 0},
                options_before={"A": "Test"},
                result={"action_type": "TEST", "time_cost": 10},
                after={"peer_action_history_size": 0},  # No peer activity
                events_created=[{"type": "PUBLIC_SYSTEM_ADVANCED", "data": {}}],
            )
        
        auditor = AutoAuditor(telemetry)
        findings = auditor.audit()
        
        dormant_findings = [f for f in findings if f["category"] == "PUBLIC_SYSTEM_PEER_DORMANT"]
        self.assertGreater(len(dormant_findings), 0)
        self.assertEqual(dormant_findings[0]["level"], "P0")
    
    def test_detect_mechanism_unreachable(self):
        """Detect missing important mechanisms"""
        telemetry = TelemetryRecorder()
        
        # Only record COMBAT actions, missing other mechanisms
        for i in range(10):
            telemetry.record_turn(
                turn=1, decision=i+1,
                requested_choice="A", actual_choice="A",
                reason_fallback=None,
                before={}, options_before={"A": "Test"},
                result={
                    "action_type": "COMBAT",
                    "time_cost": 30,
                    "leaf_actions": ["COMBAT"]
                },
                after={}, events_created=[],
            )
        
        auditor = AutoAuditor(telemetry)
        findings = auditor.audit()
        
        unreachable_findings = [f for f in findings if f["category"] == "MECHANISM_UNREACHABLE"]
        self.assertGreater(len(unreachable_findings), 0)
        self.assertIn("EXPLORATION", unreachable_findings[0]["detail"]["missing_mechanisms"])


class TestPolicies(unittest.TestCase):
    """Test policy implementations"""
    
    def test_abc_policy_cycling(self):
        """ABC policy should cycle through A, B, C"""
        policy = ABCPolicy()
        
        self.assertEqual(policy.choose(1, {"A": {}, "B": {}, "C": {}}), "A")
        self.assertEqual(policy.choose(2, {"A": {}, "B": {}, "C": {}}), "B")
        self.assertEqual(policy.choose(3, {"A": {}, "B": {}, "C": {}}), "C")
        self.assertEqual(policy.choose(4, {"A": {}, "B": {}, "C": {}}), "A")
    
    def test_abc_policy_fallback(self):
        """ABC policy should fallback when preferred not available"""
        policy = ABCPolicy()
        
        # Prefer A but only B available
        self.assertEqual(policy.choose(1, {"B": {}, "C": {}}), "B")
    
    def test_random_policy_deterministic(self):
        """Random policy with same seed should produce same results"""
        policy1 = RandomPolicy(seed=42)
        policy2 = RandomPolicy(seed=42)
        
        options = {"A": {}, "B": {}, "C": {}}
        
        # Same seed should produce same sequence
        for _ in range(10):
            self.assertEqual(policy1.choose(1, options), policy2.choose(1, options))
    
    def test_aggressive_policy_priority(self):
        """Aggressive policy should prioritize high-risk actions"""
        policy = AggressivePolicy()
        
        pending_opts = {
            "options": {
                "A": {"action": {"type": "SOCIAL_INTERACTION"}},
                "B": {"action": {"type": "COMBAT"}},
                "C": {"action": {"type": "EXPLORATION"}},
            }
        }
        
        # Should pick COMBAT or EXPLORATION (both high-risk)
        choice = policy.choose(1, {"A": {}, "B": {}, "C": {}}, pending_opts)
        self.assertIn(choice, ["B", "C"])
    
    def test_builder_policy_priority(self):
        """Builder policy should prioritize build/social actions"""
        policy = BuilderPolicy()
        
        pending_opts = {
            "options": {
                "A": {"action": {"type": "COMBAT"}},
                "B": {"action": {"type": "BUILD"}},
                "C": {"action": {"type": "SOCIAL_INTERACTION"}},
            }
        }
        
        # Should pick BUILD or SOCIAL_INTERACTION
        choice = policy.choose(1, {"A": {}, "B": {}, "C": {}}, pending_opts)
        self.assertIn(choice, ["B", "C"])
    
    def test_create_policy(self):
        """Create policy factory should work"""
        self.assertIsInstance(create_policy("abc"), ABCPolicy)
        self.assertIsInstance(create_policy("random"), RandomPolicy)
        self.assertIsInstance(create_policy("aggressive"), AggressivePolicy)
        self.assertIsInstance(create_policy("builder"), BuilderPolicy)
        
        with self.assertRaises(ValueError):
            create_policy("invalid_policy")


if __name__ == "__main__":
    unittest.main()
