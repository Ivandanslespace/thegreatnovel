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
    1. Resource quantities match context (rejects unknown resources)
    2. Stamina transitions match context (if explicitly stated)
    
    Does NOT:
    - Understand all natural language
    - Prevent all hallucinations
    - Modify game state
    
    If validation fails, raises NarrationValidationError.
    """
    if not narration or not narration.strip():
        raise NarrationValidationError("Narration is empty")
    
    # Check resource quantities (also rejects unknown resources)
    _validate_resource_quantities(context, narration)
    
    # Check stamina transitions
    _validate_stamina_transitions(context, narration)


def _validate_resource_quantities(context: NarrationContext, narration: str) -> None:
    """
    Check that resource quantities in narration match context.
    
    This guard:
    1. Extracts ALL "resource ×N" or "resource xN" patterns
    2. Rejects any resource not in the allowed set from context
    3. For known resources, verifies quantity matches
    
    Allowed resources come from:
    - inventory_before / inventory_after
    - carried_before / carried_after
    - event_payload.loot_gained (for SEARCH)
    """
    # Look for patterns like "salvage ×2" or "gold x999"
    resource_pattern = re.compile(r'(\w+)\s*[×x]\s*(\d+)', re.IGNORECASE)
    
    # Build set of allowed resources from context
    allowed_resources = set()
    allowed_resources.update(context.inventory_before.keys())
    allowed_resources.update(context.inventory_after.keys())
    allowed_resources.update(context.carried_before.keys())
    allowed_resources.update(context.carried_after.keys())
    
    # For SEARCH: add loot_gained
    if "loot_gained" in context.event_payload:
        allowed_resources.update(context.event_payload["loot_gained"].keys())
    
    for match in resource_pattern.finditer(narration):
        resource = match.group(1)
        quantity = int(match.group(2))
        
        # Reject unknown resources immediately
        if resource not in allowed_resources:
            raise NarrationValidationError(
                f"Unknown resource in narration: {resource} ×{quantity} "
                f"(allowed: {sorted(allowed_resources)})"
            )
        
        # For known resources, verify quantity
        # For SEARCH: check loot_gained in event_payload
        if context.action_type == "SEARCH" and resource in context.event_payload.get("loot_gained", {}):
            expected = context.event_payload["loot_gained"][resource]
            if quantity != expected:
                raise NarrationValidationError(
                    f"Resource quantity mismatch: {resource} ×{quantity} (expected ×{expected})"
                )
        
        # For EXTRACT: check inventory changes
        elif context.action_type == "EXTRACT" and resource in context.inventory_after:
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
