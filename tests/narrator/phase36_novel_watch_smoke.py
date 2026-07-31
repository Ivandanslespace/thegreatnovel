"""Phase 3.6 Novel Watch Smoke Test.

This smoke test demonstrates the complete Phase 3.6 flow:
1. Run autoplay to generate watch frames
2. Narrate frames using fake LLM client
3. Render novel watch output

This test uses FakeNarratorClient so it's fully deterministic and offline.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from tgn.core.models import GameState
from tgn.autoplay.runner import run_autoplay
from tgn.autoplay.policy import choose_action
from tgn.autoplay.models import AutoplayConfig
from tgn.narrator.service import NarratorService, narrate_run
from tgn.narrator.client import FakeNarratorClient
from tgn.narrator.render import render_narrated_run


def main():
    """Run Phase 3.6 novel watch smoke test."""
    print("=== Phase 3.6 Novel Watch Smoke Test ===\n")
    
    # Step 1: Create initial state
    print("Step 1: Creating initial state...")
    initial_state = GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase36-smoke",
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
    print("✓ Initial state created\n")
    
    # Step 2: Run autoplay
    print("Step 2: Running autoplay...")
    config = AutoplayConfig(max_decisions=10)
    autoplay_result = run_autoplay(
        initial_state,
        choose_action,
        config,
    )
    
    print(f"✓ Autoplay complete: {autoplay_result.decisions} decisions, {autoplay_result.events} events")
    print(f"  Stop reason: {autoplay_result.stop_reason}")
    print(f"  Frames: {len(autoplay_result.frames)}\n")
    
    # Step 3: Narrate frames with Jingxuan-style examples
    print("Step 3: Narrating frames with Jingxuan Writing Voice...")
    fake_client = FakeNarratorClient([
        "你从安全区域的边缘向下落去，绳索贴着掌心缓慢滑动，脚下原本模糊成一团的结构一点一点有了边缘，像一块沉在灰水里的铁终于浮近眼前，而你知道，在双脚真正踩上它以前，这地方仍旧只是一个名字。",
        "你把能够翻开的地方一处处翻过去，时间也跟着动作缓慢向前挪，直到那两份还能利用的材料终于从废物之间显露出来，像浓汤里忽然碰到牙齿的一小块硬物，微不足道，却足够让人立刻知道这一趟并不是空手而归；只是最后一点力气，也在这半小时里被用得干干净净。",
        "已经没有继续留下来的必要了，你带着刚找到的东西沿原路返回，身体里的疲惫并不壮烈，它只是沉，安静地坠在四肢末端，直到安全区域重新把你包进去，那两份材料从'找到'变成'拥有'，这趟短得几乎没有故事的旅程，才算真正结束。",
    ])
    service = NarratorService(fake_client)
    
    narration_result = narrate_run(autoplay_result, service)
    
    print(f"✓ Narration complete: {len(narration_result.narrated_frames)} frames narrated")
    print(f"  Failures: {narration_result.narration_failures}\n")
    
    # Step 4: Render novel output
    print("Step 4: Rendering novel watch output...")
    novel_output = render_narrated_run(narration_result)
    
    print("✓ Novel output rendered\n")
    print("=" * 60)
    print(novel_output)
    print("=" * 60)
    print()
    
    # Step 5: Verify key properties
    print("Step 5: Verifying key properties...")
    
    # Check game state unchanged
    from tgn.core.hashing import state_hash
    final_hash = state_hash(autoplay_result.final_state.__dict__)
    assert narration_result.source_final_hash == final_hash
    print("✓ Game state hash unchanged by narration")
    
    # Check information boundary
    from tgn.narrator.context import build_narration_context
    drop_context = build_narration_context(autoplay_result.frames[0])
    assert "salvage" not in str(drop_context.event_payload)
    print("✓ DROP context doesn't contain future salvage")
    
    search_context = build_narration_context(autoplay_result.frames[1])
    assert "salvage" in search_context.event_payload.get("loot_gained", {})
    print("✓ SEARCH context contains discovered salvage")
    
    print("\n=== PHASE 3.6 SMOKE TEST PASSED ===")
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
