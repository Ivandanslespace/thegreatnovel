"""Unified validation layer - both aggregate and strict modes.

This module provides:
1. Aggregate mode for repair passes (collect all errors)
2. Strict mode for final compilation (fail fast with full context)
3. Shared validation functions to avoid schema drift
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union


# Reuse PRIMARY_ATTRIBUTES from here (central definition)
PRIMARY_ATTRIBUTES = {"strength", "constitution", "agility", "spirit"}

EVENT_FAMILIES = {
    "rule_anomaly",
    "macro_crisis", 
    "forced_convergence",
    "story_arc",
    "daily_routine",
}


class ValidationError(Exception):
    """Structured validation error with path information."""
    
    def __init__(self, code: str, path: str, message: str, detail: dict = None):
        self.code = code
        self.path = path
        self.message = message
        self.detail = detail
        super().__init__(f"[{code}] {path}: {message}")


class ValidationContext:
    """Holds all collected validation issues."""
    
    def __init__(self):
        self.issues: List[Dict[str, Any]] = []
    
    def add(self, code: str, path: str, message: str, detail: dict = None):
        issue = {
            "code": code,
            "path": path,
            "message": message,
        }
        if detail:
            issue["detail"] = detail
        self.issues.append(issue)
    
    def has_p0(self) -> bool:
        """Check if there are any blocking issues."""
        return any(
            i["code"] in ("MISSING_REQUIRED_FIELD", "INVALID_TYPE", "VALUE_OUT_OF_RANGE", "SCHEMA_MISMATCH")
            for i in self.issues
        )
    
    def raise_first(self):
        """Raise the first P0 error as exception."""
        if self.issues:
            raise ValidationError(
                self.issues[0]["code"],
                self.issues[0]["path"],
                self.issues[0]["message"],
                self.issues[0].get("detail")
            )
    
    def summary(self) -> str:
        if not self.issues:
            return "✓ All valid"
        
        by_code = {}
        for issue in self.issues:
            code = issue["code"]
            by_code[code] = by_code.get(code, 0) + 1
        
        lines = ["Validation failed:", ""]
        for code, count in sorted(by_code.items()):
            lines.append(f"  - {code}: {count} occurrences")
        
        lines.append("\nDetails:")
        for i, issue in enumerate(self.issues, 1):
            lines.append(f"{i}. [{issue['code']}] {issue['path']}")
            lines.append(f"   {issue['message']}")
        
        return "\n".join(lines)


def _require_field(ctx: ValidationContext, value: Any, path: str, required: bool = True):
    """Check if required field is present."""
    if value is None or value == "":
        if required:
            ctx.add("MISSING_REQUIRED_FIELD", path, "Field cannot be empty")
        return False
    return True


def _require_number(ctx: ValidationContext, value: Any, path: str, minimum: float = None):
    """Check if field is a valid number."""
    try:
        num = float(value)
        if minimum is not None and num < minimum:
            ctx.add("VALUE_OUT_OF_RANGE", path, f"Value {num} must be >= {minimum}")
            return False
        return True
    except (TypeError, ValueError):
        ctx.add("INVALID_TYPE", path, f"Expected number, got {type(value).__name__}")
        return False


def _normalize_capabilities(capabilities_raw: dict, ctx: ValidationContext) -> dict:
    """Normalize capabilities: ensure explicit true/false for each feature.
    
    CRITICAL FIX: This addresses the schema inconsistency where:
    - Template uses null meaning "LLM will define"  
    - Compiler treats null as False (bool(None) == False)
    
    NEW RULE: Capabilities MUST be explicitly defined as true/false at world creation time.
    None/null is NOT allowed because it silently becomes False and breaks expectations.
    
    Also fixes the "disaster/disasters" naming inconsistency by normalizing to "disasters".
    """
    if not isinstance(capabilities_raw, dict):
        ctx.add("INVALID_TYPE", 
               "world.mechanics.capabilities",
               "Must be an object with true/false values for each capability")
        return {}
    
    result = {}
    
    # Normalize each capability - must be explicit boolean, never null
    for key in ("combat", "building", "crafting", "factions", "disasters"):
        val = capabilities_raw.get(key)
        
        if val is None:
            # CRITICAL: Reject null/None - must be explicitly true or false
            ctx.add("MISSING_REQUIRED_FIELD",
                   f"world.mechanics.capabilities.{key}",
                   f"Capability must be explicitly defined as true or false (not null)")
            # Default to False to allow compilation to continue
            result[key] = False
        elif isinstance(val, bool):
            result[key] = val
        else:
            # Try to interpret string values
            if isinstance(val, str):
                result[key] = val.lower() in ("true", "yes", "enabled", "1")
            else:
                result[key] = False
    
    # Fix common typo: disasters vs disaster (use plural as canonical)
    if "disaster" in capabilities_raw and "disasters" not in capabilities_raw:
        ctx.add("SCHEMA_MISMATCH",
               "world.mechanics.capabilities.disaster",
               "Use 'disasters' (plural) not 'disaster' (singular)")
        # Accept both but warn
        if "capabilities_raw" in capabilities_raw:
            result["disasters"] = capabilities_raw["disaster"]
    
    return result


def validate_location(ctx: ValidationContext, record: dict, location_ids: set[str]):
    """Validate single location record."""
    loc_id = record.get("id", "unknown")
    label = f"world_blueprint.locations.{loc_id}"
    
    for field in ("safe", "discovered", "travel_minutes_from_base", "travel_stamina_from_base", 
                 "extraction_minutes", "extraction_stamina_cost"):
        if field not in record:
            ctx.add("MISSING_REQUIRED_FIELD", f"{label}.{field}", 
                   f"Location schema mismatch: {field} is required")
    
    for field in ("travel_minutes_from_base", "travel_stamina_from_base", 
                 "extraction_minutes", "extraction_stamina_cost"):
        if field in record:
            _require_number(ctx, record[field], f"{label}.{field}")


def validate_action_target(ctx: ValidationContext, record: dict, location_ids: set[str]):
    """Validate single action target record."""
    target_id = record.get("id", "unknown")
    label = f"world_blueprint.action_targets.{target_id}"
    
    # Compiler requires ALL these fields
    for field in ("name", "action_type", "location_id", "primary_attribute", 
                 "target_difficulty", "time_minutes", "stamina_cost", "mental_cost", 
                 "effects"):
        if field not in record or record[field] in (None, ""):
            ctx.add("MISSING_REQUIRED_FIELD", 
                   f"{label}.{field}",
                   "Required field is missing (compiler requirement)")
    
    if "location_id" in record:
        if str(record["location_id"]) not in location_ids:
            ctx.add("INVALID_VALUE", f"{label}.location_id", 
                   f"Location ID '{record['location_id']}' not registered")
    
    if "primary_attribute" in record:
        if str(record["primary_attribute"]) not in PRIMARY_ATTRIBUTES:
            ctx.add("INVALID_VALUE", f"{label}.primary_attribute", 
                   f"Attribute '{record['primary_attribute']}' not supported")
    
    for field in ("target_difficulty", "time_minutes", "stamina_cost", "mental_cost"):
        if field in record:
            _require_number(ctx, record[field], f"{label}.{field}")
    
    # Special validation for effects structure
    if "effects" in record:
        effects = record["effects"]
        if not isinstance(effects, dict):
            ctx.add("INVALID_TYPE", f"{label}.effects", 
                   "Must be an object with success/partial_failure/failure keys")
        elif not any(effects.get(branch) for branch in ("success", "partial_failure", "failure")):
            ctx.add("MISSING_REQUIRED_FIELD", f"{label}.effects", 
                   "At least one outcome branch (success/partial_failure/failure) must have content")
