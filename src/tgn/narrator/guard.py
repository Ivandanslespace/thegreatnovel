"""Hallucination guard for narrator output."""

from __future__ import annotations

import re
from typing import Any

from .models import NarrationContext


class NarrationValidationError(Exception):
    """Raised when narration fails validation."""
    pass


def validate_narration(context: NarrationContext, narration: str) -> None:
    """
    Validate narration against context to detect hallucinations.
    
    This is a MINIMAL deterministic guard. It cannot understand all natural language,
    but it catches obvious numerical/resource tampering.
    
    Checks:
    1. Resource quantities match context (if explicitly stated)
    2. Stamina transitions match context (if explicitly stated)
    3. No unknown system rewards (if pattern detected)
    
    Does NOT:
    - Understand all natural language
    - Prevent all hallucinations
    - Modify game state
    
    If validation fails, raises NarrationValidationError.
    """
    if not narration or not narration.strip():
        raise NarrationValidationError("Narration is empty")
    
    # Check resource quantities
    _validate_resource_quantities(context, narration)
    
    # Check stamina transitions
    _validate_stamina_transitions(context, narration)
    
    # Check for unknown system rewards
    _validate_no_unknown_rewards(context, narration)


def _validate_resource_quantities(context: NarrationContext, narration: str) -> None:
    """Check that explicitly stated resource quantities match context."""
    # Look for patterns like "salvage ×2" or "salvage x 2"
    resource_pattern = re.compile(r'(\w+)\s*[×x]\s*(\d+)', re.IGNORECASE)
    
    for match in resource_pattern.finditer(narration):
        resource = match.group(1)
        quantity = int(match.group(2))
        
        # Check if this resource exists in context
        # For SEARCH: check loot_gained in event_payload
        if context.action_type == "SEARCH" and resource in context.event_payload.get("loot_gained", {}):
            expected = context.event_payload["loot_gained"][resource]
            if quantity != expected:
                raise NarrationValidationError(
                    f"Resource quantity mismatch: {resource} ×{quantity} (expected ×{expected})"
                )
        
        # For EXTRACT: check inventory changes
        elif context.action_type == "EXTRACT":
            if resource in context.inventory_after:
                before = context.inventory_before.get(resource, 0)
                after = context.inventory_after[resource]
                expected = after - before
                if quantity != expected:
                    raise NarrationValidationError(
                        f"Resource quantity mismatch: {resource} ×{quantity} (expected ×{expected})"
                    )


def _validate_stamina_transitions(context: NarrationContext, narration: str) -> None:
    """Check that explicitly stated stamina transitions match context."""
    # Look for patterns like "体力：3 → 2" or "stamina: 3 -> 2"
    # Use (?:→|->|- >) to match different arrow styles
    stamina_pattern = re.compile(r'(?:体力|stamina)[:：]\s*(\d+)\s*(?:→|->|- >)\s*(\d+)', re.IGNORECASE)
    
    for match in stamina_pattern.finditer(narration):
        before = int(match.group(1))
        after = int(match.group(2))
        
        if before != context.stamina_before or after != context.stamina_after:
            raise NarrationValidationError(
                f"Stamina transition mismatch: {before}→{after} "
                f"(expected {context.stamina_before}→{context.stamina_after})"
            )


def _validate_no_unknown_rewards(context: NarrationContext, narration: str) -> None:
    """Check for unknown system rewards that weren't in context."""
    # Look for reward patterns like "获得：gold ×10" or "入库：crystal ×5"
    reward_pattern = re.compile(r'(?:获得|入库|携带)[:：]\s*(\w+)\s*[×x]\s*(\d+)', re.IGNORECASE)
    
    for match in reward_pattern.finditer(narration):
        resource = match.group(1)
        
        # Check if this resource is mentioned in context
        known_resources = set()
        
        # Add resources from inventory
        known_resources.update(context.inventory_before.keys())
        known_resources.update(context.inventory_after.keys())
        
        # Add resources from carried loot
        known_resources.update(context.carried_before.keys())
        known_resources.update(context.carried_after.keys())
        
        # Add resources from event payload
        if "loot_gained" in context.event_payload:
            known_resources.update(context.event_payload["loot_gained"].keys())
        
        if resource not in known_resources:
            raise NarrationValidationError(
                f"Unknown reward resource: {resource} (not in context)"
            )
