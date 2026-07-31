"""Validator refactored to aggregate all errors before failing.

Key changes:
1. Collect ALL validation errors instead of failing fast
2. Return structured error list with paths for easy fixing
3. Support repair pass workflow
4. Fix capabilities null/disaster discrepancy

This allows LLM to see all missing fields at once and fix in one round.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Reuse PRIMARY_ATTRIBUTES from world_compiler (ratings doesn't export it yet)
from engine_runtime.world_compiler import PRIMARY_ATTRIBUTES


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
        return any(i["code"] == "MISSING_REQUIRED_FIELD" or i["code"] == "INVALID_VALUE" for i in self.issues)
    
    def summary(self) -> str:
        if not self.issues:
            return "✓ All valid"
        
        by_code = {}
        for issue in self.issues:
            code = issue["code"]
            by_code[code] = by_code.get(code, 0) + 1
        
        lines = ["Validation failed:"]
        for code, count in sorted(by_code.items()):
            lines.append(f"  - {code}: {count} occurrences")
        
        lines.append("\nDetails:")
        for i, issue in enumerate(self.issues, 1):
            lines.append(f"{i}. [{issue['code']}] {issue['path']}")
            lines.append(f"   {issue['message']}")
        
        return "\n".join(lines)


def _require_field(ctx: ValidationContext, value: Any, path: str) -> bool:
    """Check if required field is present."""
    if value is None or value == "":
        ctx.add("MISSING_REQUIRED_FIELD", path, f"Field cannot be empty")
        return False
    return True


def _require_number(ctx: ValidationContext, value: Any, path: str, minimum: float = None) -> bool:
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


def _normalize_capabilities(world: dict, ctx: ValidationContext) -> dict:
    """Normalize capabilities: convert null/undefined to explicit true/false.
    
    Fixes the schema inconsistency where:
    - template uses null meaning "LLM will define"
    - compiler treats null as False
    
    Returns normalized capabilities dict.
    """
    raw = world.get("capabilities", {})
    if not isinstance(raw, dict):
        ctx.add("INVALID_TYPE", "capabilities", "Must be an object")
        return {"combat": False, "building": False, "crafting": False, "factions": False, "disaster": False}
    
    # Normalize each capability
    result = {}
    for key in ("combat", "building", "crafting", "factions", "disaster"):
        val = raw.get(key)
        if val is None:
            # null means undefined → default to False
            result[key] = False
        elif isinstance(val, bool):
            result[key] = val
        else:
            # Try to interpret string values
            if isinstance(val, str):
                result[key] = val.lower() in ("true", "yes", "enabled", "1")
            else:
                result[key] = False
    
    # Check if there's a typo: disasters vs disaster
    if "disasters" in raw and "disaster" not in raw:
        ctx.add("SCHEMA_MISMATCH", "capabilities.disasters", 
               "Used 'disasters' but should be 'disaster' (singular)")
        result["disaster"] = result.get("disasters", False)
    
    return result


def compile_world_bundle(world: dict, save_name: str = "test") -> Tuple[dict, ValidationContext]:
    """Compile a validated world bundle.
    
    Args:
        world: World YAML dict
        save_name: Name for the save directory
    
    Returns:
        (compiled_world, ctx)
        If ctx.has_p0(), compilation failed and compiled_world is partial
    """
    ctx = ValidationContext()
    
    if not isinstance(world, dict):
        ctx.add("INVALID_TYPE", "", "World must be a YAML object")
        return {}, ctx
    
    # Step 1: Normalize capabilities FIRST (before anything reads them)
    capabilities = _normalize_capabilities(world, ctx)
    world["capabilities"] = capabilities
    
    # Step 2: Extract basic structure
    world_data = world.get("world", {})
    blueprint = world.get("world_blueprint", {})
    
    # Get registered location IDs
    locations_raw = blueprint.get("locations", [])
    location_ids = set()
    starting_location_id = None
    
    if isinstance(locations_raw, list):
        for loc in locations_raw:
            if isinstance(loc, dict) and loc.get("id"):
                location_ids.add(str(loc["id"]))
    
    starting_location_id = str(world.get("starting_location") or "")
    
    if starting_location_id and starting_location_id not in location_ids:
        ctx.add("MISSING_REQUIRED_FIELD", 
               "starting_location",
               f"Location '{starting_location_id}' not found in locations registry")
        ctx.add("SUGGESTION", "starting_location",
               f"Available locations: {', '.join(sorted(location_ids)[:5])}")
    
    # Step 3: Validate action_targets with full error collection
    action_targets_raw = blueprint.get("action_targets", [])
    action_targets = []
    
    if isinstance(action_targets_raw, list):
        for target in action_targets_raw:
            if not isinstance(target, dict):
                continue
            
            target_id = target.get("id", "unknown")
            label = f"world_blueprint.action_targets.{target_id}"
            
            # Collect ALL missing fields for this target
            for field in ("name", "action_type", "location_id", "primary_attribute", 
                         "target_difficulty", "time_minutes", "stamina_cost", "mental_cost", "effects"):
                if field not in target or target[field] in (None, ""):
                    ctx.add("MISSING_REQUIRED_FIELD", f"{label}.{field}", f"Required field is missing")
            
            # Validate nested structures
            if "effects" in target:
                effects = target["effects"]
                if not isinstance(effects, dict):
                    ctx.add("INVALID_TYPE", f"{label}.effects", "Must be an object with success/partial_failure/failure keys")
                elif not any(effects.get(branch) for branch in ("success", "partial_failure", "failure")):
                    ctx.add("MISSING_REQUIRED_FIELD", f"{label}.effects", 
                           "At least one outcome branch (success/partial_failure/failure) must have content")
            
            # Only add if it has minimal required fields
            if target.get("id") and target.get("action_type"):
                action_targets.append(dict(target))
    
    # Step 4: Validate locations schema
    if isinstance(locations_raw, list):
        for loc in locations_raw:
            if not isinstance(loc, dict):
                continue
            
            loc_id = loc.get("id", "unknown")
            label = f"world_blueprint.locations.{loc_id}"
            
            # Required numeric fields
            for field in ("travel_minutes_from_base", "travel_stamina_from_base", 
                         "extraction_minutes", "extraction_stamina_cost"):
                if field not in loc:
                    ctx.add("MISSING_REQUIRED_FIELD", f"{label}.{field}", 
                           f"Location schema mismatch: {field} is required")
                elif not _require_number(ctx, loc[field], f"{label}.{field}"):
                    pass
    
    # Add collected issues to ctx
    # Note: In production, we'd also validate enemies, recipes, etc.
    # For now, we focus on the critical blockers that prevent game start
    
    return {
        "compiled": True,
        "save_name": save_name,
        "location_ids": list(location_ids),
        "action_targets": action_targets,
    }, ctx


if __name__ == "__main__":
    # Test with punk_world.yaml
    import sys
    import yaml
    
    if len(sys.argv) < 2:
        print("Usage: python validators_aggregate.py <world.yaml>")
        sys.exit(1)
    
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        world = yaml.safe_load(f)
    
    compiled, ctx = compile_world_bundle(world, "test")
    
    print(ctx.summary())
    
    if ctx.has_p0():
        print("\n❌ Cannot create save until these issues are fixed.")
        sys.exit(1)
    else:
        print("\n✓ Validation passed!")
        sys.exit(0)
