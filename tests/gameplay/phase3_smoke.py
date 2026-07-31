"""Phase 3 Smoke Test - Minimal verification of expedition vertical slice."""

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, 'src')

from tgn.core.models import GameState
from tgn.actions.models import ActionIntent
from tgn.gameplay.expedition import execute_action
from tgn.storage import EventStore, verify_persistence_integrity


print("=== Phase 3 Smoke Test ===")
print()

with TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / "phase3_smoke.db"
    
    # Setup
    store = EventStore(db_path)
    try:
        state = GameState.initial(seed="phase3-smoke")
        state.data["player"] = {
            "location_id": "base-1",
            "stamina": 3,
            "max_stamina": 3,
        }
        state.data["inventory"] = {}
        state.data["expedition"] = {
            "active": False,
            "base_location_id": "base-1",
            "target_location_id": "site-1",
            "target_searched": False,
            "target_loot": {"salvage": 2},
            "carried_loot": {},
        }
        store.initialize("camp_phase3", state.__dict__)
        
        print(f"✓ Initialized campaign at {db_path}")
        
        # Initial legal actions check
        from tgn.gameplay.expedition import get_legal_actions
        initial_actions = get_legal_actions(state)
        print(f"\nInitial legal actions: {initial_actions}")
        assert "WAIT" in initial_actions
        assert "DROP" in initial_actions
        
        # DROP
        drop_result = execute_action(state, ActionIntent("drop-001", "player", "DROP", {}))
        print(f"\n✓ DROP accepted={drop_result.accepted}")
        print(f"  event_seq={drop_result.events[0].event_seq}, decision_seq={drop_result.events[0].decision_seq}")
        print(f"  location={drop_result.final_state.data['player']['location_id']}")
        print(f"  stamina={drop_result.final_state.data['player']['stamina']}")
        
        final_state_1 = drop_result.final_state
        store.append_transition("camp_phase3", drop_result.events[0], state, final_state_1)
        
        # Second action check
        actions_after_drop = get_legal_actions(final_state_1)
        print(f"\nPost-DROP legal actions: {actions_after_drop}")
        assert "SEARCH" in actions_after_drop
        assert "EXTRACT" in actions_after_drop
        assert "DROP" not in actions_after_drop
        
        # SEARCH
        search_result = execute_action(final_state_1, ActionIntent("search-001", "player", "SEARCH", {}))
        print(f"\n✓ SEARCH accepted={search_result.accepted}")
        print(f"  event_seq={search_result.events[0].event_seq}, decision_seq={search_result.events[0].decision_seq}")
        print(f"  carried_loot={search_result.final_state.data['expedition']['carried_loot']}")
        print(f"  inventory={search_result.final_state.data['inventory']}")
        
        final_state_2 = search_result.final_state
        store.append_transition("camp_phase3", search_result.events[0], final_state_1, final_state_2)
        
        # Third action check  
        actions_after_search = get_legal_actions(final_state_2)
        print(f"\nPost-SEARCH legal actions: {actions_after_search}")
        assert "EXTRACT" in actions_after_search
        assert "SEARCH" not in actions_after_search
        
        # EXTRACT
        extract_result = execute_action(final_state_2, ActionIntent("extract-001", "player", "EXTRACT", {}))
        print(f"\n✓ EXTRACT accepted={extract_result.accepted}")
        print(f"  event_seq={extract_result.events[0].event_seq}, decision_seq={extract_result.events[0].decision_seq}")
        print(f"  location={extract_result.final_state.data['player']['location_id']}")
        print(f"  inventory={extract_result.final_state.data['inventory']}")
        print(f"  carried_loot={extract_result.final_state.data['expedition']['carried_loot']}")
        
        final_state_3 = extract_result.final_state
        store.append_transition("camp_phase3", extract_result.events[0], final_state_2, final_state_3)
        
        # Final stats
        print(f"\nFinal state:")
        print(f"  game_minute={final_state_3.game_minute}")
        print(f"  event_seq={final_state_3.event_seq}")
        print(f"  decision_seq={final_state_3.decision_seq}")
        
    finally:
        store.close()
    
    print(f"\n✓ Persisted 3 events to database")
    
    print("\nReopening database...")
    
    # Reopen and verify
    new_store = EventStore(db_path)
    try:
        verify_result = verify_persistence_integrity("camp_phase3", db_path)
        
        if verify_result.success:
            print(f"\n✓ Persistence verification SUCCESS=True")
            print(f"  Final hash matches: {verify_result.actual_hash == verify_result.expected_hash}")
            
            # Verify hashes match action execution results
            from tgn.core.hashing import state_hash
            action_hash = state_hash(final_state_3.__dict__)
            replay_hash = verify_result.actual_hash
            
            if action_hash == replay_hash:
                print(f"  ✓ Hash from action execution matches persisted replay: {action_hash[:16]}...")
            else:
                print(f"  ✗ HASH MISMATCH!")
                sys.exit(1)
        else:
            print(f"\n✗ VERIFICATION FAILED: {verify_result.error_message}")
            sys.exit(1)
            
    finally:
        new_store.close()

print("\n=== PHASE 3 SMOKE TEST PASSED ===")
