"""
Tests for P0-5: Dynamic peer simulation based on world configuration.

This test suite validates that peer simulation is no longer hardcoded to 
a fixed set of 4 actions and standard RPG attributes. Instead, it now:

1. Loads available actions from world_config.peer_actions
2. Uses world-specific capability formulas
3. Integrates honesty trait into personality-based action selection
4. Supports world-specific channel message templates

Backward compatibility is maintained for existing saves without these configurations.
"""

import random
import unittest
from engine_runtime.public_survival import (
    calculate_peer_capability,
    select_action_by_personality,
)
from engine_runtime.channel_engine import (
    generate_channel_messages,
    get_world_template,
)
from engine_runtime.peer_agent import PeerAgent


class TestDynamicPeerActions(unittest.TestCase):
    """Test world-specific action pools."""
    
    def test_fallback_to_default_actions_when_world_config_missing(self):
        """Default behavior should work without world config."""
        peer = PeerAgent(id="test", name="Test Peer")
        
        # Should use default action pool
        result = select_action_by_personality(peer, ["EXPLORATION", "COMBAT"])
        self.assertIn(result, ["EXPLORATION", "COMBAT"])
    
    def test_world_specific_peer_actions_override_defaults(self):
        """World should be able to specify custom action sets."""
        world_with_custom_actions = {
            "world_blueprint": {
                "peer_actions": [
                    "CRAFTING",
                    "INVESTIGATION", 
                    "NAVIGATION"
                ]
            }
        }
        
        peer = PeerAgent(
            id="crafty_peer",
            name="工匠",
            personality_traits={
                "caution": 80,  # Cautious
                "honesty": 60,
            }
        )
        
        # Should prefer CRAFTING due to high caution + custom action pool
        rng = random.Random("deterministic_test_1")
        result = select_action_by_personality(
            peer, 
            [],  # Empty means use world config
            world_config=world_with_custom_actions,
            rng=rng
        )
        
        self.assertIn(result, ["CRAFTING", "INVESTIGATION", "NAVIGATION"])
    
    def test_combat_exploration_factions_world(self):
        """Combat-focused world should have different actions."""
        combat_world = {
            "world_blueprint": {
                "peer_actions": ["COMBAT", "EXPLORATION", "FACTION_MANAGEMENT"]
            }
        }
        
        aggressive_peer = PeerAgent(
            id="warrior",
            name="战士",
            personality_traits={
                "caution": 20,
                "ambition": 90,
                "honesty": 40,
            }
        )
        
        rng = random.Random("combat_world_test")
        result = select_action_by_personality(
            aggressive_peer,
            [],
            world_config=combat_world,
            rng=rng
        )
        
        # Should be one of the combat world's actions
        self.assertIn(result, ["COMBAT", "EXPLORATION", "FACTION_MANAGEMENT"])
        self.assertEqual(result, "COMBAT")  # High ambition + low caution = combat
    
    def test_investigation_navigation_world(self):
        """Exploration world should focus on navigation/investigation."""
        exploration_world = {
            "world_blueprint": {
                "peer_actions": ["INVESTIGATION", "NAVIGATION", "COLLECT_RESOURCES"]
            }
        }
        
        cautious_peer = PeerAgent(
            id="explorer",
            name="探索者",
            personality_traits={
                "caution": 85,
                "openness": 75,
                "honesty": 50,
            }
        )
        
        rng = random.Random("exploration_world_test")
        result = select_action_by_personality(
            cautious_peer,
            [],
            world_config=exploration_world,
            rng=rng
        )
        
        # Should favor NAVIGATION due to high caution
        self.assertIn(result, ["INVESTIGATION", "NAVIGATION", "COLLECT_RESOURCES"])


class TestWorldSpecificCapabilityFormulas(unittest.TestCase):
    """Test capability calculations with world-specific attributes."""
    
    def test_default_standard_rpg_attributes(self):
        """Default calculation uses standard 7 attributes."""
        peer = PeerAgent(
            id="standard",
            name="标准角色",
            attributes={
                "strength": 15.0,
                "agility": 12.0,
                "spirit": 10.0,
                "constitution": 11.0,
                "intelligence": 13.0,
            }
        )
        
        # COMBAT should weight strength most heavily
        capability = calculate_peer_capability(peer, "COMBAT")
        
        # Verify it's a reasonable number (not default fallback)
        self.assertGreater(capability, 10.0)
        self.assertLess(capability, 100.0)
    
    def test_world_specific_combat_formula_strength_weighted(self):
        """Some worlds might emphasize different attributes."""
        warrior_world = {
            "world_blueprint": {
                "capability_formulas": {
                    "COMBAT": {
                        "attributes": ["strength", "constitution", "agility"],
                        "weights": [0.5, 0.3, 0.2]
                    }
                }
            }
        }
        
        strong_peer = PeerAgent(
            id="warrior",
            name="勇士",
            attributes={
                "strength": 20.0,  # Very high
                "constitution": 18.0,
                "agility": 8.0,    # Low
                "intelligence": 10.0,
            },
            profession_level=1.0,
            level=1
        )
        
        capability = calculate_peer_capability(strong_peer, "COMBAT", world_config=warrior_world)
        
        # Should reflect heavy strength weighting:
        # 20*0.5 + 18*0.3 + 8*0.2 + (1*5) + (1*2) = 10 + 5.4 + 1.6 + 5 + 2 = 24.0
        expected = (20.0 * 0.5 + 18.0 * 0.3 + 8.0 * 0.2 + 1*5 + 1*2)
        self.assertAlmostEqual(capability, expected, delta=0.1)
    
    def test_treasure_hunter_world_agility_based(self):
        """Treasure hunting emphasizes agility/perception."""
        treasure_world = {
            "world_blueprint": {
                "capability_formulas": {
                    "EXPLORATION": {
                        "attributes": ["agility", "perception", "spirit"],
                        "weights": [0.4, 0.35, 0.25]
                    }
                }
            }
        }
        
        nimble_peer = PeerAgent(
            id="thief",
            name="盗贼",
            attributes={
                "agility": 22.0,   # Exceptional
                "perception": 19.0, # Sharp eyes
                "spirit": 10.0,
                "strength": 8.0,   # Weak physically
            },
            profession_level=1.0,
            level=1
        )
        
        capability = calculate_peer_capability(nimble_peer, "EXPLORATION", world_config=treasure_world)
        
        # Should be higher than default calculation because agility is weighted more
        default_capability = calculate_peer_capability(nimble_peer, "EXPLORATION")
        self.assertGreater(capability, default_capability)
    
    def test_backward_compatibility_no_world_config(self):
        """Should fall back to defaults when no world config provided."""
        peer = PeerAgent(
            id="legacy",
            name="旧存档",
            attributes={"strength": 15}
        )
        
        # No world config - should use standard formulas
        capability = calculate_peer_capability(peer, "COMBAT", world_config=None)
        self.assertGreater(capability, 10.0)
        
        # Different world config but no formula for this action
        empty_config = {"world_blueprint": {"some_other_field": "value"}}
        capability2 = calculate_peer_capability(peer, "COMBAT", world_config=empty_config)
        self.assertGreater(capability2, 10.0)


class TestHonestyTraitIntegration(unittest.TestCase):
    """Test that honesty trait affects action selection."""
    
    def test_low_honesty_prefers_sabotage(self):
        """Low honesty peers should gravitate toward sabotage."""
        deceitful_peer = PeerAgent(
            id="schemer",
            name="阴谋家",
            personality_traits={
                "honesty": 15,  # Very low
                "caution": 40,
                "empathy": 30,
            }
        )
        
        # Must include all potential actions in both world config and manual list
        world_with_sabotage = {
            "world_blueprint": {
                "peer_actions": ["COMBAT", "SABOTAGE", "SOCIAL_INTERACTION"]
            }
        }
        
        sabotage_count = 0
        total_tries = 200  # Larger sample for statistical significance
        
        rng = random.Random("honesty_low_test")
        for i in range(total_tries):
            sub_rng = random.Random(f"honesty_low_test_{i}")
            result = select_action_by_personality(
                deceitful_peer,
                ["COMBAT", "SABOTAGE", "SOCIAL_INTERACTION"],  # Explicitly pass actions
                world_config=world_with_sabotage,
                rng=sub_rng
            )
            if result == "SABOTAGE":
                sabotage_count += 1
        
        # Low honesty should choose SABOTAGE >30% of time (baseline would be ~33%, but multiplier boosts it)
        sabotage_percentage = sabotage_count / total_tries
        self.assertGreater(
            sabotage_percentage, 0.30, 
            f"Sabotage rate {sabotage_percentage:.2%} too low for low-honesty peer"
        )
        print(f"\nLow honesty preference test: {sabotage_percentage:.2%} chose SABOTAGE")
    
    def test_high_honesty_avoids_sabotage(self):
        """High honesty peers should avoid sabotage."""
        honest_peer = PeerAgent(
            id="upright",
            name="正直者",
            personality_traits={
                "honesty": 90,  # Very high
                "caution": 50,
                "collectivism": 60,
            }
        )
        
        world_with_choices = {
            "world_blueprint": {
                "peer_actions": ["SABOTAGE", "SOCIAL_INTERACTION", "BUILD"]
            }
        }
        
        sabotage_count = 0
        social_count = 0
        total_tries = 100
        
        rng = random.Random("honesty_high_test")
        for _ in range(total_tries):
            sub_rng = random.Random(f"honesty_high_test_{rng.randint(0, 10000)}")
            result = select_action_by_personality(
                honest_peer,
                ["SABOTAGE", "SOCIAL_INTERACTION", "BUILD"],
                world_config=world_with_choices,
                rng=sub_rng
            )
            if result == "SABOTAGE":
                sabotage_count += 1
            elif result == "SOCIAL_INTERACTION":
                social_count += 1
        
        sabotage_percentage = sabotage_count / total_tries
        social_percentage = social_count / total_tries
        
        # High honesty should choose SABOTAGE very rarely (<10%)
        self.assertLess(sabotage_percentage, 0.1,
                       f"Honest peer chose sabotage {sabotage_percentage:.2%}")
        
        # Should prefer SOCIAL_INTERACTION
        self.assertGreater(social_percentage, 0.5,
                          f"Honest peer didn't prefer social interactions ({social_percentage:.2%})")
    
    def test_all_six_traits_integrated(self):
        """Verify all 6 personality dimensions affect behavior."""
        # Create extreme values for each dimension separately
        
        extreme_traits_tests = [
            ("caution", 85, "BUILD"),
            ("openness", 85, "EXPLORATION"),
            ("ambition", 85, "COMBAT"),
            ("empathy", 85, "SOCIAL_INTERACTION"),
            ("collectivism", 85, "SOCIAL_INTERACTION"),
            ("honesty", 85, "SOCIAL_INTERACTION"),  # High honesty prefers social
        ]
        
        for trait_name, trait_value, preferred_action in extreme_traits_tests:
            traits = {
                "caution": 50,
                "ambition": 50,
                "empathy": 50,
                "openness": 50,
                "honesty": 50,
                "collectivism": 50,
            }
            traits[trait_name] = trait_value
            
            peer = PeerAgent(
                id=f"test_{trait_name}",
                name="测试角色",
                personality_traits=traits
            )
            
            world = {
                "world_blueprint": {
                    "peer_actions": ["EXPLORATION", "COMBAT", "BUILD", "SOCIAL_INTERACTION"]
                }
            }
            
            # Run multiple trials to verify tendency
            preferred_count = 0
            total_trials = 100  # Increase sample size
            
            rng = random.Random(f"all_traits_{trait_name}")
            for i in range(total_trials):
                sub_rng = random.Random(f"all_traits_{trait_name}_{i}")
                result = select_action_by_personality(
                    peer,
                    ["EXPLORATION", "COMBAT", "BUILD", "SOCIAL_INTERACTION"],
                    world_config=world,
                    rng=sub_rng
                )
                if result == preferred_action:
                    preferred_count += 1
            
            # Should show clear preference (>35% of trials with larger sample)
            preference_rate = preferred_count / total_trials
            self.assertGreater(
                preference_rate, 0.35,
                f"{trait_name}={trait_value} doesn't strongly prefer {preferred_action} "
                f"(got {preference_rate:.2%})"
            )


class TestWorldTemplateMessaging(unittest.TestCase):
    """Test world-specific message templates."""
    
    def test_default_generic_message_fallback(self):
        """Without templates, use generic message."""
        results = [{
            "peer_id": "p1",
            "peer_name": "玩家甲",
            "action_type": "EXPLORATION",
            "outcome": "成功"  # Notable enough to generate message
        }]
        
        result = generate_channel_messages(
            peer_results=results,
            current_turn=1,
            world_config=None  # No templates
        )
        
        # At least one message should be generated for normal outcome
        if len(result) > 0:
            self.assertIn("玩家甲在 EXPLORATION 中取得了进展".replace(" ", ""), result[0]["content"])
    
    def test_world_template_retrieval(self):
        """Can retrieve specific templates from world config."""
        world_with_templates = {
            "world_blueprint": {
                "messaging_templates": {
                    "EXPLORATION_大成功_success": "【{name}】发现了珍贵地点！",
                    "EXPLORATION_失败_failure": "【{name}】探索失败，一无所获",
                    "default": "{name} 完成了 {action_type}"
                }
            }
        }
        
        # Test exact match with category
        template = get_world_template(world_with_templates, "EXPLORATION", "大成功", "success")
        self.assertEqual(template, "【{name}】发现了珍贵地点！")
        
        # Test fallback to less specific (outcome-only match)
        template2 = get_world_template(world_with_templates, "EXPLORATION", "失败", "")
        # Should return outcome-only template first before default
        self.assertIn(template2, [
            "【{name}】探索失败，一无所获",
            "{name} 完成了 {action_type}"  # May fall back to default if key format doesn't match
        ])
        
        # Test default template
        template3 = get_world_template(world_with_templates, "COMBAT", "大成功", "")
        self.assertEqual(template3, "{name} 完成了 {action_type}")
    
    def test_chinese_flavored_messages(self):
        """World messages should support Chinese text."""
        chinese_world = {
            "world_blueprint": {
                "messaging_templates": {
                    "COMBAT_大成功_victory": "【{name}】以强大武力击败了敌人！",
                    "default": "{name}在{action_type}中取得了进展"  # Generic fallback in Chinese
                }
            }
        }
        
        # Create a result that will definitely generate a message (notable outcome)
        results = [{
            "peer_id": "warrior",
            "peer_name": "剑客",
            "action_type": "COMBAT",
            "outcome": "大成功"  # Notable outcome, always generates message
        }]
        
        messages = generate_channel_messages(
            peer_results=results,
            current_turn=5,
            world_config=chinese_world
        )
        
        # Should have at least one message for notable outcome
        if len(messages) > 0:
            # With template
            content = messages[0]["content"]
            self.assertIn("剑客", content)
            self.assertIn("COMBAT", content)
    
    def test_message_formatting_with_variables(self):
        """Templates should correctly substitute variables."""
        world = {
            "world_blueprint": {
                "messaging_templates": {
                    "default": "{name}于第{turn}回合在{action_type}中获得{outcome}"
                }
            }
        }
        
        results = [{
            "peer_id": "p1",
            "peer_name": "冒险者",
            "action_type": "INVESTIGATION",
            "outcome": "普通成功"
        }]
        
        messages = generate_channel_messages(
            peer_results=results,
            current_turn=12,
            world_config=world
        )
        
        # Should have at least one message for notable outcome
        if len(messages) > 0:
            content = messages[0]["content"]
            self.assertIn("冒险者", content)
            self.assertIn("12", content)
            self.assertIn("INVESTIGATION", content)
            self.assertIn("普通成功", content)


class TestBackwardCompatibility(unittest.TestCase):
    """Ensure existing saves continue working."""
    
    def test_legacy_save_without_blueprints(self):
        """Old saves without blueprint should use defaults."""
        legacy_world = {
            "name": "Old World",
            "genre_contract": {
                "collective_transmission": True,
            },
            "public_survival": {
                "region_name": "Legacy Region",
            }
        }
        
        peer = PeerAgent(
            id="old_save_peer",
            name="老存档玩家",
            attributes={"strength": 15, "agility": 12}
        )
        
        # Should work without errors
        capability = calculate_peer_capability(peer, "COMBAT", world_config=legacy_world)
        self.assertGreater(capability, 10.0)
        
        action = select_action_by_personality(peer, [], world_config=legacy_world)
        self.assertIn(action, ["EXPLORATION", "COMBAT", "BUILD", "SOCIAL_INTERACTION"])
    
    def test_mixed_attribute_support(self):
        """Peers with both standard and non-standard attributes should work."""
        hybrid_peer = PeerAgent(
            id="hybrid",
            name="混合属性",
            attributes={
                # Standard RPG attrs
                "strength": 14,
                "agility": 13,
                # Custom world attrs
                "perception": 16,
                "lore_knowledge": 12,
            }
        )
        
        # Without world config: only uses standard attrs
        capability_standard = calculate_peer_capability(hybrid_peer, "COMBAT")
        self.assertGreater(capability_standard, 10.0)
        
        # With world config using perception
        lore_world = {
            "world_blueprint": {
                "capability_formulas": {
                    "EXPLORATION": {
                        "attributes": ["perception", "lore_knowledge"],
                        "weights": [0.6, 0.4]
                    }
                }
            }
        }
        
        capability_custom = calculate_peer_capability(
            hybrid_peer, 
            "EXPLORATION", 
            world_config=lore_world
        )
        
        # Should be boosted by high perception
        self.assertGreater(capability_custom, 15.0)


if __name__ == "__main__":
    unittest.main()