"""Fail-closed validation for lazy world expansion candidates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ..hashing import sha256_json


def _invalid(reason: str, request: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    result = {"valid": False, "reason_code": reason, "request": deepcopy(dict(request))}
    result.update(extra)
    return result


def validate_expansion(compiled: Mapping[str, Any], expansion_id: str, candidate: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a candidate against the sealed expansion schema.

    Every failure is converted to a structured result.  The function never
    mutates ``compiled`` and never allows a candidate to rewrite its parent.
    """

    expansion = next((item for item in compiled.get("expansions", ()) if item.get("id") == expansion_id), None)
    if expansion is None:
        return {"valid": False, "reason_code": "unknown_expansion", "expansion_id": expansion_id}
    candidate_schema = expansion["candidate"]
    request = {
        "type": "expansion_request",
        "expansion_id": expansion_id,
        "parent_hash": compiled["blueprint_hash"],
        "anchors": deepcopy(expansion["anchors"]),
        "namespace": candidate_schema["namespace"],
    }
    if candidate is None:
        return request
    try:
        if not isinstance(candidate, Mapping):
            return _invalid("invalid_candidate", request)
        value = deepcopy(dict(candidate))
        allowed = {"parent_hash", "namespace", "anchors", "state_patches", "actions", "processes", "milestones"}
        required = set(allowed)
        unknown = set(value) - allowed
        missing = required - set(value)
        if unknown:
            return _invalid("unknown_candidate_field", request, fields=sorted(unknown))
        if missing:
            return _invalid("missing_candidate_field", request, fields=sorted(missing))
        if value["parent_hash"] != compiled["blueprint_hash"]:
            return _invalid("parent_hash_mismatch", request)
        if value["namespace"] != candidate_schema["namespace"]:
            return _invalid("namespace_mismatch", request)
        if value["anchors"] != expansion["anchors"]:
            return _invalid("anchor_mismatch", request)

        # Reuse the blueprint validator's exact action/process/milestone and
        # patch/fact language.  Imports are lazy to avoid blueprint's public
        # convenience re-export creating an import cycle.
        from ..blueprint import _action, _patches, _validate_milestones, _validate_processes

        _patches(value["state_patches"], "candidate.state_patches")
        if not isinstance(value["actions"], list) or not isinstance(value["processes"], list) or not isinstance(value["milestones"], list):
            return _invalid("invalid_candidate_collection", request)
        for index, item in enumerate(value["actions"]):
            _action(item, f"candidate.actions[{index}]")
        _validate_processes(value["processes"])
        _validate_milestones(value["milestones"])

        expected = candidate_schema
        for collection in ("actions", "processes", "milestones"):
            actual_ids = [item["id"] for item in value[collection]]
            expected_ids = [item["id"] for item in expected[collection]]
            if actual_ids != expected_ids:
                return _invalid("candidate_ids_mismatch", request, collection=collection, expected=expected_ids, actual=actual_ids)
            if len(actual_ids) != len(set(actual_ids)):
                return _invalid("duplicate_candidate_id", request, collection=collection)
            for ident in actual_ids:
                if not isinstance(ident, str) or not ident:
                    return _invalid("invalid_candidate_id", request, collection=collection)

        return {
            "valid": True,
            "expansion_id": expansion_id,
            "parent_hash": compiled["blueprint_hash"],
            "namespace": value["namespace"],
            "candidate": value,
            "candidate_hash": sha256_json(value),
            "request": request,
        }
    except Exception as exc:  # fail closed: malformed candidates never escape
        return _invalid("invalid_candidate", request, error=type(exc).__name__)
