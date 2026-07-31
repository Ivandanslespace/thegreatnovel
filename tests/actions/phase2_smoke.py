"""Phase 2 Smoke Test - Minimal verification."""

import sys
sys.path.insert(0, 'src')

from tgn.core.models import GameState
from tgn.actions.models import ActionIntent
from tgn.actions.validation import execute_action

print("=== Phase 2 Smoke Test ===")
print()

# First WAIT 60
state = GameState.initial()
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

state2 = result.final_state
assert state2 is not None

# Second WAIT 30
intent2 = ActionIntent(
    action_id="smoke-2",
    actor_id="player",
    action_type="WAIT",
    params={"minutes": 30}
)

result2 = execute_action(state2, intent2)
print(f"✓ WAIT 30 accepted={result2.accepted}")
print(f"  event_seq={result2.events[0].event_seq}, decision_seq={result2.events[0].decision_seq}, game_minute={result2.events[0].game_minute}")

assert result2.accepted
assert result2.events[0].event_seq == 2
assert result2.events[0].decision_seq == 2
assert result2.events[0].game_minute == 90

print()
print("=== SMOKE TEST PASSED ===")
