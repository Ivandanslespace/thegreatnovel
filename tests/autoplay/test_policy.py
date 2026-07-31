"""Policy tests per spec section #37."""

import pytest
from tgn.autoplay.policy import choose_action
from tgn.gameplay.expedition import build_observation, execute_action
from tgn.actions.models import ActionIntent


class TestPolicy:
    """Deterministic policy tests."""
    
    def test_policy_selects_drop_at_initial_base(self, phase35_initial_state):
        """At initial base, policy selects DROP."""
        obs = build_observation(phase35_initial_state)
        intent = choose_action(obs, 1)
        
        assert intent is not None
        assert intent.action_type == "DROP"
        assert intent.action_id == "auto-action-0001"
    
    def test_policy_selects_search_after_drop(self, phase35_initial_state):
        """After DROP, policy selects SEARCH."""
        obs = build_observation(phase35_initial_state)
        drop_intent = choose_action(obs, 1)
        result = execute_action(phase35_initial_state, drop_intent)
        
        obs_after = build_observation(result.final_state)
        search_intent = choose_action(obs_after, 2)
        
        assert search_intent is not None
        assert search_intent.action_type == "SEARCH"
        assert search_intent.action_id == "auto-action-0002"
    
    def test_policy_selects_extract_after_search(self, phase35_initial_state):
        """After SEARCH, policy selects EXTRACT."""
        obs = build_observation(phase35_initial_state)
        drop_intent = choose_action(obs, 1)
        drop_result = execute_action(phase35_initial_state, drop_intent)
        
        obs_after_drop = build_observation(drop_result.final_state)
        search_intent = choose_action(obs_after_drop, 2)
        search_result = execute_action(drop_result.final_state, search_intent)
        
        obs_after_search = build_observation(search_result.final_state)
        extract_intent = choose_action(obs_after_search, 3)
        
        assert extract_intent is not None
        assert extract_intent.action_type == "EXTRACT"
        assert extract_intent.action_id == "auto-action-0003"
    
    def test_policy_stops_when_only_wait_remains(self, phase35_initial_state):
        """After EXTRACT (only WAIT remains), policy returns None."""
        obs = build_observation(phase35_initial_state)
        drop_intent = choose_action(obs, 1)
        drop_result = execute_action(phase35_initial_state, drop_intent)
        
        obs_after_drop = build_observation(drop_result.final_state)
        search_intent = choose_action(obs_after_drop, 2)
        search_result = execute_action(drop_result.final_state, search_intent)
        
        obs_after_search = build_observation(search_result.final_state)
        extract_intent = choose_action(obs_after_search, 3)
        extract_result = execute_action(search_result.final_state, extract_intent)
        
        obs_after_extract = build_observation(extract_result.final_state)
        stop_intent = choose_action(obs_after_extract, 4)
        
        assert stop_intent is None
    
    def test_policy_is_deterministic(self, phase35_initial_state):
        """Same observation produces same action."""
        obs = build_observation(phase35_initial_state)
        
        intent1 = choose_action(obs, 1)
        intent2 = choose_action(obs, 1)
        
        assert intent1.action_type == intent2.action_type
        assert intent1.action_id == intent2.action_id
        assert intent1.actor_id == intent2.actor_id
    
    def test_policy_receives_observation_not_game_state(self, phase35_initial_state):
        """Policy must receive observation dict, not GameState."""
        obs = build_observation(phase35_initial_state)
        
        # Verify observation structure
        assert isinstance(obs, dict)
        assert "legal_actions" in obs
        assert "location_id" in obs
        assert "stamina" in obs
        
        # Verify target_loot is NOT in observation
        assert "target_loot" not in obs
        
        # Policy should work with observation
        intent = choose_action(obs, 1)
        assert intent is not None
