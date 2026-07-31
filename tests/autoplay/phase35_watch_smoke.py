"""Phase 3.5 watch smoke test per spec section #44."""

import tempfile
from pathlib import Path

from tgn.autoplay import (
    run_autoplay,
    AutoplayConfig,
    choose_action,
    render_run,
    write_run_jsonl,
)
from tgn.core.models import GameState
from tgn.storage.event_store import EventStore
from tgn.storage import verify_persistence_integrity


def main():
    """Run Phase 3.5 watch smoke test."""
    print("=== Phase 3.5 Watch Smoke Test ===\n")
    
    # Create canonical initial state
    initial_state = GameState(
        schema_version=1,
        event_seq=0,
        decision_seq=0,
        game_minute=0,
        seed="phase35-smoke",
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
    
    # Run autoplay with persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "smoke.db"
        campaign_id = "smoke-campaign"
        
        # Run autoplay (initializes campaign internally)
        store = EventStore(db_path)
        config = AutoplayConfig()
        result = run_autoplay(
            initial_state,
            choose_action,
            config,
            event_store=store,
            campaign_id=campaign_id,
        )
        
        store.close()
        
        # Render watch output
        watch_output = render_run(result)
        print(watch_output)
        print()
        
        # Export JSONL
        jsonl_path = Path(tmpdir) / "run.jsonl"
        write_run_jsonl(result, jsonl_path)
        print(f"JSONL exported to: {jsonl_path.name}")
        print()
        
        # Verify persistence
        print("Verifying persistence...")
        verification = verify_persistence_integrity(campaign_id, db_path)
        
        if verification.success:
            print("✓ Persistence verification: SUCCESS")
        else:
            print("✗ Persistence verification: FAILED")
            return False
        
        # Verify hashes match
        store2 = EventStore(db_path)
        from tgn.core.hashing import state_hash
        action_hash = state_hash(result.final_state.__dict__)
        replay_hash = verification.actual_hash
        store2.close()
        
        if action_hash == replay_hash:
            print(f"✓ Persisted hash matches RunResult hash: {action_hash[:16]}...")
        else:
            print("✗ Hash mismatch")
            print(f"  Action hash: {action_hash[:16]}...")
            print(f"  Replay hash: {replay_hash[:16]}...")
            return False
        
        print()
        print("=== PHASE 3.5 SMOKE TEST PASSED ===")
        return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
