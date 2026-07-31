"""Phase 2 Smoke Test - Complete with persistence verification."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, 'src')

from tgn.core.models import GameState
from tgn.actions.models import ActionIntent
from tgn.actions.validation import execute_action
from tgn.storage import EventStore, verify_persistence_integrity

print("=== Phase 2 Smoke Test ===")
print()

with TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "smoke.db"
    
    # Setup
    store = EventStore(db_path)
    try:
        state = GameState.initial(seed="smoke-test")
        store.initialize("camp_smoke", state.__dict__)
        print(f"✓ Initialized campaign at {db_path}")
        
        # First WAIT 60
        intent = ActionIntent(
            action_id="smoke-1",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 60}
        )
        
        result = execute_action(state, intent)
        print(f"✓ WAIT 60 accepted={result.accepted}")
        print(f"  event_seq={result.events[0].event_seq}, decision_seq={result.events[0].decision_seq}, game_minute={result.events[0].game_minute}")
        print(f"  action_id={result.events[0].action_id}")
        
        final_state_1 = result.final_state
        store.append_transition("camp_smoke", result.events[0], state, final_state_1)
        
        # Second WAIT 30
        intent2 = ActionIntent(
            action_id="smoke-2",
            actor_id="player",
            action_type="WAIT",
            params={"minutes": 30}
        )
        
        result2 = execute_action(final_state_1, intent2)
        print(f"✓ WAIT 30 accepted={result2.accepted}")
        print(f"  event_seq={result2.events[0].event_seq}, decision_seq={result2.events[0].decision_seq}, game_minute={result2.events[0].game_minute}")
        
        final_state_2 = result2.final_state
        store.append_transition("camp_smoke", result2.events[0], final_state_1, final_state_2)
        print(f"✓ Persisted 2 events to database")
        
    finally:
        store.close()
    
    print()
    print("Reopening database...")
    
    # Reopen and verify
    new_store = EventStore(db_path)
    try:
        verify_result = verify_persistence_integrity("camp_smoke", db_path)
        
        if verify_result.success:
            print(f"✓ Persistence verification SUCCESS=True")
            print(f"  Final hash matches: {verify_result.actual_hash == verify_result.expected_hash}")
            
            # Verify hashes match action execution results
            from tgn.core.hashing import state_hash
            action_hash = state_hash(final_state_2.__dict__)
            replay_hash = verify_result.actual_hash
            
            if action_hash == replay_hash:
                print(f"✓ Hash from action execution matches persisted replay: {action_hash[:16]}...")
            else:
                print(f"✗ HASH MISMATCH!")
                sys.exit(1)
        else:
            print(f"✗ VERIFICATION FAILED: {verify_result.error_message}")
            sys.exit(1)
            
    finally:
        new_store.close()

print()
print("=== SMOKE TEST PASSED ===")

