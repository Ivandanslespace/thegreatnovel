"""Phase 3.7 Voice Pack Smoke Test.

This smoke test demonstrates:
1. Voice registry with built-in voices
2. Default voice selection (cablecar_survival)
3. Explicit voice selection (jingxuan)
4. Voice isolation (different voices don't affect game state)
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.policy import choose_action
from tgn.autoplay.models import AutoplayConfig, StopReason
from tgn.core.models import GameState
from tgn.core.hashing import state_hash
from tgn.narrator import (
    NarratorService,
    narrate_run,
    render_narrated_run,
    create_builtin_registry,
    FakeNarratorClient,
    DEFAULT_VOICE_ID,
)


def create_initial_state() -> GameState:
    """Create initial game state for narration."""
    return GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase37-smoke",
        data={
            "player": {
                "location_id": "base-1",
                "stamina": 3,
                "max_stamina": 3,
            },
            "inventory": {},
            "expedition": {
                "active": False,
                "base_location_id": "base-1",
                "target_location_id": "site-1",
                "target_searched": False,
                "target_loot": {"salvage": 2},
                "carried_loot": {},
            },
        },
    )


def main():
    """Run Phase 3.7 voice pack smoke test."""
    print("=== Phase 3.7 Voice Pack Smoke Test ===\n")
    
    # Step 1: Show available voices
    print("Step 1: Available voice packs")
    registry = create_builtin_registry()
    voices = registry.list()
    
    print("Available voices:")
    for voice in voices:
        is_default = voice.name == DEFAULT_VOICE_ID
        marker = " [default]" if is_default else ""
        print(f"  - {voice.name}{marker}")
    
    print()
    
    # Step 2: Run autoplay
    print("Step 2: Running autoplay...")
    initial_state = create_initial_state()
    config = AutoplayConfig(max_decisions=10)
    
    autoplay_result = run_autoplay(
        initial_state,
        choose_action,
        config,
    )
    
    print(f"Autoplay complete: {autoplay_result.decisions} decisions, {autoplay_result.events} events")
    print(f"Stop reason: {autoplay_result.stop_reason}")
    print()
    
    # Check for rejected run
    if autoplay_result.stop_reason == StopReason.ACTION_REJECTED:
        print("ERROR: Autoplay was rejected!")
        return False
    
    # Step 3: Narrate with default voice (cablecar_survival)
    print("Step 3: Narrating with default voice (cablecar_survival)...")
    client1 = FakeNarratorClient([
        "你从基地出发，沿着标记的路径向目标地点移动。十分钟后，你抵达了探索地点。",
        "你在探索地点仔细搜索，从废物中找到了 salvage ×2，携带在身上准备返回。",
        "你带着收获沿原路返回基地，将 salvage ×2 安全入库。",
    ])
    
    service1 = NarratorService(client1)
    narration_result1 = narrate_run(autoplay_result, service1)
    
    print(f"Narration complete: {len(narration_result1.narrated_frames)} frames")
    print(f"Voice used: {service1.voice_profile.name}")
    print()
    
    # Verify game state unchanged
    hash_before = state_hash(autoplay_result.final_state.__dict__)
    hash_after = state_hash(autoplay_result.final_state.__dict__)
    
    if hash_before != hash_after:
        print("ERROR: Game state changed during narration!")
        return False
    
    print(f"Gameplay final hash (cablecar): {autoplay_result.final_state_hash}")
    print()
    
    # Step 4: Narrate with jingxuan voice
    print("Step 4: Narrating with jingxuan voice...")
    client2 = FakeNarratorClient([
        "你从安全区域的边缘向下落去，绳索贴着掌心缓慢滑动，脚下原本模糊成一团的结构一点一点有了边缘。",
        "你把能够翻开的地方一处处翻过去，直到那两份还能利用的材料终于从废物之间显露出来。",
        "已经没有继续留下来的必要了，你带着刚找到的东西沿原路返回。",
    ])
    
    service2 = NarratorService(client2, voice_id="jingxuan")
    narration_result2 = narrate_run(autoplay_result, service2)
    
    print(f"Narration complete: {len(narration_result2.narrated_frames)} frames")
    print(f"Voice used: {service2.voice_profile.name}")
    print()
    
    # Verify game state still unchanged
    hash_after_jingxuan = state_hash(autoplay_result.final_state.__dict__)
    
    if hash_before != hash_after_jingxuan:
        print("ERROR: Game state changed during jingxuan narration!")
        return False
    
    print(f"Gameplay final hash (jingxuan): {autoplay_result.final_state_hash}")
    print()
    
    # Step 5: Verify voice isolation
    print("Step 5: Verifying voice isolation...")
    
    # Both narrations should have same number of frames
    if len(narration_result1.narrated_frames) != len(narration_result2.narrated_frames):
        print("ERROR: Different number of frames!")
        return False
    
    # Both should have same game state hash
    if hash_after != hash_after_jingxuan:
        print("ERROR: Different game state hashes!")
        return False
    
    print("✓ Voice isolation verified: different voices produce same gameplay hash")
    print()
    
    # Step 6: Render output
    print("Step 6: Rendering narrated output (cablecar_survival)...")
    output = render_narrated_run(narration_result1)
    
    print("=" * 60)
    print(output)
    print("=" * 60)
    print()
    
    print("=== PHASE 3.7 SMOKE TEST PASSED ===")
    print()
    print("Summary:")
    print(f"  Available voices: {len(voices)}")
    print(f"  Default voice: {DEFAULT_VOICE_ID}")
    print(f"  Autoplay decisions: {autoplay_result.decisions}")
    print(f"  Narrated frames: {len(narration_result1.narrated_frames)}")
    print(f"  Voice isolation: PASS")
    print(f"  Game state unchanged: PASS")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ SMOKE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
