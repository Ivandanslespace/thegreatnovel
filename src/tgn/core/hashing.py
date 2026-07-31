"""Canonical state hashing for deterministic replay."""

import hashlib
import json
from typing import Any


class DeterministicHashError(Exception):
    """Raised when state cannot be deterministically hashed."""
    pass


def canonical_json(value: Any) -> str:
    """
    Convert Python value to canonical JSON string.
    
    Requirements:
    - sort_keys=True: dict key order doesn't matter
    - separators: no whitespace
    - ensure_ascii=False: preserve Unicode
    - allow_nan=False: reject NaN/Infinity
    
    This ensures:
    {"a": 1, "b": 2} == {"b": 2, "a": 1} in hash
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def state_hash(state: dict[str, Any]) -> str:
    """
    Calculate SHA-256 hash of a game state.
    
    Args:
        state: GameState dictionary (must be JSON serializable without NaN)
        
    Returns:
        Hex digest of SHA-256 hash
        
    Raises:
        DeterministicHashError: if state contains NaN/Infinity or is not serializable
    """
    try:
        canonical = canonical_json(state)
    except (TypeError, ValueError) as e:
        raise DeterministicHashError(f"State contains non-serializable values: {e}")
    
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_canonicalizability(state: dict[str, Any]) -> None:
    """
    Verify that a state can be converted to canonical JSON.
    
    Useful for pre-validation before storing events.
    """
    try:
        canonical_json(state)
    except (TypeError, ValueError) as e:
        raise DeterministicHashError(f"State is not canonicalizable: {e}")
