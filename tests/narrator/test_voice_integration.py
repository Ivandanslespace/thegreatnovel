"""Integration tests for voice selection and narration."""

import pytest
from tgn.narrator import (
    NarratorService,
    narrate_run,
    FakeNarratorClient,
    create_builtin_registry,
    DEFAULT_VOICE_ID,
    VoiceNotFoundError,
)
from tgn.autoplay.models import AutoplayRunResult, StopReason, WatchFrame
from tgn.core.hashing import state_hash


@pytest.fixture
def sample_run_result():
    """Create a sample AutoplayRunResult with 3 frames."""
    frames = (
        WatchFrame(
            step=0,
            action_id="action-001",
            actor_id="bot-001",
            action_type="DROP",
            event_type="EXPEDITION_DROPPED",
            game_minute_before=0,
            game_minute_after=10,
            observation_before={
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
                "inventory": {},
                "carried_loot": {},
            },
            observation_after={
                "location_id": "site-1",
                "stamina": 2,
                "max_stamina": 3,
                "inventory": {},
                "carried_loot": {},
            },
            event_payload={
                "destination": "site-1",
                "time": 10,
                "stamina_cost": 1,
            },
            state_hash_before="hash_before_0",
            state_hash_after="hash_after_0",
        ),
        WatchFrame(
            step=1,
            action_id="action-002",
            actor_id="bot-001",
            action_type="SEARCH",
            event_type="SEARCH_RESOLVED",
            game_minute_before=10,
            game_minute_after=40,
            observation_before={
                "location_id": "site-1",
                "stamina": 2,
                "max_stamina": 3,
                "inventory": {},
                "carried_loot": {},
            },
            observation_after={
                "location_id": "site-1",
                "stamina": 0,
                "max_stamina": 3,
                "inventory": {},
                "carried_loot": {"salvage": 2},
            },
            event_payload={
                "loot_gained": {"salvage": 2},
                "time": 30,
                "stamina_cost": 2,
            },
            state_hash_before="hash_before_1",
            state_hash_after="hash_after_1",
        ),
        WatchFrame(
            step=2,
            action_id="action-003",
            actor_id="bot-001",
            action_type="EXTRACT",
            event_type="EXPEDITION_EXTRACTED",
            game_minute_before=40,
            game_minute_after=55,
            observation_before={
                "location_id": "site-1",
                "stamina": 0,
                "max_stamina": 3,
                "inventory": {},
                "carried_loot": {"salvage": 2},
            },
            observation_after={
                "location_id": "base-1",
                "stamina": 0,
                "max_stamina": 3,
                "inventory": {"salvage": 2},
                "carried_loot": {},
            },
            event_payload={
                "destination": "base-1",
                "time": 15,
                "stamina_cost": 0,
            },
            state_hash_before="hash_before_2",
            state_hash_after="hash_after_2",
        ),
    )
    
    return AutoplayRunResult(
        completed=True,
        stop_reason=StopReason.POLICY_COMPLETE,
        initial_state_hash="initial_hash",
        final_state_hash="final_hash",
        decisions=3,
        events=3,
        frames=frames,
        final_state=None,
    )


class TestVoiceSelectionIntegration:
    """Tests for voice selection with NarratorService."""
    
    def test_default_voice_is_cablecar(self, sample_run_result):
        """NarratorService uses cablecar_survival by default."""
        client = FakeNarratorClient([
            "Narration 1",
            "Narration 2",
            "Narration 3",
        ])
        
        service = NarratorService(client)
        
        # Should use default voice
        assert service.voice_profile.name == DEFAULT_VOICE_ID
        assert service.voice_profile.name == "cablecar_survival"
    
    def test_explicit_voice_selection(self, sample_run_result):
        """Can explicitly select a voice."""
        client = FakeNarratorClient([
            "Narration 1",
            "Narration 2",
            "Narration 3",
        ])
        
        service = NarratorService(client, voice_id="jingxuan")
        
        assert service.voice_profile.name == "jingxuan"
    
    def test_unknown_voice_raises_error(self):
        """Selecting unknown voice raises VoiceNotFoundError."""
        client = FakeNarratorClient([])
        
        with pytest.raises(VoiceNotFoundError) as exc_info:
            NarratorService(client, voice_id="nonexistent")
        
        assert "nonexistent" in str(exc_info.value)
    
    def test_narrate_run_with_default_voice(self, sample_run_result):
        """narrate_run works with default voice."""
        client = FakeNarratorClient([
            "Narration 1",
            "Narration 2",
            "Narration 3",
        ])
        
        service = NarratorService(client)
        result = narrate_run(sample_run_result, service)
        
        assert len(result.narrated_frames) == 3
        assert result.narration_failures == 0
    
    def test_narrate_run_with_jingxuan_voice(self, sample_run_result):
        """narrate_run works with jingxuan voice."""
        client = FakeNarratorClient([
            "Narration 1",
            "Narration 2",
            "Narration 3",
        ])
        
        service = NarratorService(client, voice_id="jingxuan")
        result = narrate_run(sample_run_result, service)
        
        assert len(result.narrated_frames) == 3
        assert result.narration_failures == 0
    
    def test_different_voices_produce_different_prompts(self, sample_run_result):
        """Different voices produce different prompts."""
        # Track prompts sent to client
        prompts_cablecar = []
        prompts_jingxuan = []
        
        class PromptCapturingClient:
            def __init__(self, prompts_list):
                self.prompts_list = prompts_list
                self.call_count = 0
            
            def generate(self, prompt):
                self.prompts_list.append(prompt)
                self.call_count += 1
                return f"Narration {self.call_count}"
        
        client1 = PromptCapturingClient(prompts_cablecar)
        service1 = NarratorService(client1, voice_id="cablecar_survival")
        narrate_run(sample_run_result, service1)
        
        client2 = PromptCapturingClient(prompts_jingxuan)
        service2 = NarratorService(client2, voice_id="jingxuan")
        narrate_run(sample_run_result, service2)
        
        # Prompts should be different
        assert len(prompts_cablecar) == 3
        assert len(prompts_jingxuan) == 3
        
        # Check that voice sections differ
        for p1, p2 in zip(prompts_cablecar, prompts_jingxuan):
            # Both should have voice sections
            assert "WRITING VOICE" in p1
            assert "WRITING VOICE" in p2
            
            # But different voice names
            assert "CABLECAR SURVIVAL" in p1
            assert "JINGXUAN" in p2
            
            # Facts should be identical
            # Extract fact sections (everything before WRITING VOICE)
            facts1 = p1.split("WRITING VOICE")[0]
            facts2 = p2.split("WRITING VOICE")[0]
            assert facts1 == facts2
    
    def test_voice_does_not_affect_game_state_hash(self, sample_run_result):
        """Different voices produce same game state hash."""
        from tgn.core.models import GameState
        
        # Create a real game state
        final_state = GameState(
            schema_version=1,
            event_seq=3,
            decision_seq=3,
            game_minute=55,
            seed="test",
            data={
                "player": {
                    "location_id": "base-1",
                    "stamina": 0,
                    "max_stamina": 3,
                },
                "inventory": {"salvage": 2},
                "expedition": {
                    "active": False,
                    "base_location_id": "base-1",
                    "target_location_id": "site-1",
                    "target_searched": True,
                    "target_loot": {},
                    "carried_loot": {},
                },
            },
        )
        
        # Create new run result with real final state
        final_state_hash = state_hash(final_state.__dict__)
        run_result_with_state = AutoplayRunResult(
            completed=sample_run_result.completed,
            stop_reason=sample_run_result.stop_reason,
            initial_state_hash=sample_run_result.initial_state_hash,
            final_state_hash=final_state_hash,
            decisions=sample_run_result.decisions,
            events=sample_run_result.events,
            frames=sample_run_result.frames,
            final_state=final_state,
        )
        
        # Hash before narration
        hash_before = state_hash(final_state.__dict__)
        
        # Narrate with cablecar
        client1 = FakeNarratorClient(["N1", "N2", "N3"])
        service1 = NarratorService(client1, voice_id="cablecar_survival")
        narrate_run(run_result_with_state, service1)
        
        # Hash after cablecar narration
        hash_after_cablecar = state_hash(final_state.__dict__)
        
        # Narrate with jingxuan
        client2 = FakeNarratorClient(["N1", "N2", "N3"])
        service2 = NarratorService(client2, voice_id="jingxuan")
        narrate_run(run_result_with_state, service2)
        
        # Hash after jingxuan narration
        hash_after_jingxuan = state_hash(final_state.__dict__)
        
        # All hashes should be identical
        assert hash_before == hash_after_cablecar
        assert hash_before == hash_after_jingxuan
        assert hash_after_cablecar == hash_after_jingxuan
    
    def test_registry_isolation(self, sample_run_result):
        """NarratorService uses provided registry."""
        from tgn.narrator.voice import VoiceRegistry, WritingVoiceProfile
        
        # Create custom registry
        custom_registry = VoiceRegistry()
        custom_voice = WritingVoiceProfile(
            name="custom",
            instructions="Custom instructions"
        )
        custom_registry.register(custom_voice)
        
        client = FakeNarratorClient(["N1", "N2", "N3"])
        
        # Use custom registry
        service = NarratorService(
            client,
            voice_id="custom",
            voice_registry=custom_registry
        )
        
        assert service.voice_profile.name == "custom"
        
        # Built-in voices should not be available in custom registry
        with pytest.raises(VoiceNotFoundError):
            NarratorService(client, voice_id="jingxuan", voice_registry=custom_registry)


class TestVoiceFactPriority:
    """Tests ensuring facts always override voice."""
    
    def test_fact_section_precedes_voice_section(self, sample_run_result):
        """FACTS section appears before WRITING VOICE in prompt."""
        prompts = []
        
        class PromptCapturingClient:
            def generate(self, prompt):
                prompts.append(prompt)
                return "Narration"
        
        client = PromptCapturingClient()
        service = NarratorService(client, voice_id="cablecar_survival")
        
        # Narrate first frame only
        service.narrate_frame(sample_run_result.frames[0])
        
        assert len(prompts) == 1
        prompt = prompts[0]
        
        # Find positions
        facts_pos = prompt.find("FACTS")
        voice_pos = prompt.find("WRITING VOICE")
        
        assert facts_pos != -1
        assert voice_pos != -1
        assert facts_pos < voice_pos
    
    def test_non_negotiable_rules_precede_voice(self, sample_run_result):
        """NON-NEGOTIABLE FACT RULES appears before WRITING VOICE."""
        prompts = []
        
        class PromptCapturingClient:
            def generate(self, prompt):
                prompts.append(prompt)
                return "Narration"
        
        client = PromptCapturingClient()
        service = NarratorService(client, voice_id="jingxuan")
        
        service.narrate_frame(sample_run_result.frames[0])
        
        assert len(prompts) == 1
        prompt = prompts[0]
        
        # Find positions
        rules_pos = prompt.find("NON-NEGOTIABLE")
        voice_pos = prompt.find("WRITING VOICE")
        
        assert rules_pos != -1
        assert voice_pos != -1
        assert rules_pos < voice_pos
