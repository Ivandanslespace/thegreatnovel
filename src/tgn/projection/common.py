"""Small local helpers for the bounded Phase 9B2A projection boundary."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..core.hashing import canonical_json
from ..worldgen.models import ValidationIssue, WorldGenError


SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class _StrictJSONError(ValueError):
    """Internal parse failure with a stable boundary code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _StrictJSONError("INVALID_JSON", f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise _StrictJSONError(
        "NON_CANONICAL_JSON_VALUE",
        f"non-standard JSON number: {value}",
    )


def _find_nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_find_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(_find_nonfinite(item) for item in value)
    return False


def contains_surrogate(value: str) -> bool:
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def surrogate_code_points(value: str) -> list[str]:
    return sorted(
        {f"U+{ord(character):04X}" for character in value if 0xD800 <= ord(character) <= 0xDFFF}
    )


def safe_issue_text(value: str) -> str:
    if contains_surrogate(value):
        return "contains invalid Unicode surrogate " + ", ".join(
            surrogate_code_points(value)
        )
    return value


def safe_issue_value(value: Any) -> Any:
    """Make issue payloads safe even when the rejected value is not UTF-8-safe."""

    if isinstance(value, str):
        if contains_surrogate(value):
            return {"invalid_code_points": surrogate_code_points(value)}
        return value
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        return {"invalid_number": repr(value)}
    if isinstance(value, Mapping):
        safe_mapping: dict[str, Any] = {}
        for key, item in value.items():
            key_text = key if isinstance(key, str) else str(key)
            safe_mapping[safe_issue_text(key_text)] = safe_issue_value(item)
        return safe_mapping
    if isinstance(value, (list, tuple)):
        return [safe_issue_value(item) for item in value]
    return {"invalid_value_type": type(value).__name__}


def assert_canonical_utf8(value: Any) -> None:
    """Internal invariant for every successful or reported boundary value."""

    canonical_json(value).encode("utf-8")


def canonical_payload(value: Any) -> str:
    payload = canonical_json(value)
    payload.encode("utf-8")
    return payload


def sha256_json(value: Any) -> str:
    import hashlib

    return hashlib.sha256(canonical_payload(value).encode("utf-8")).hexdigest()


def parse_strict_json(payload: str) -> Any:
    if not isinstance(payload, str):
        raise _StrictJSONError("INVALID_JSON", "JSON payload must be text")
    try:
        parsed = json.loads(
            payload,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except _StrictJSONError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _StrictJSONError("INVALID_JSON", "payload is not valid JSON") from exc
    if _find_nonfinite(parsed):
        raise _StrictJSONError(
            "NON_CANONICAL_JSON_VALUE",
            "JSON contains a non-finite number",
        )
    return parsed


def issue(
    code: str,
    path: str,
    message: str,
    expected: Any = None,
    actual: Any = None,
    allowed_values: Any = None,
) -> ValidationIssue:
    result = ValidationIssue(
        code=safe_issue_text(code),
        path=safe_issue_text(path),
        message=safe_issue_text(message),
        expected=safe_issue_value(expected),
        actual=safe_issue_value(actual),
        allowed_values=safe_issue_value(allowed_values),
    )
    assert_canonical_utf8(result.to_dict())
    return result


def sort_issues(issues: Iterable[ValidationIssue]) -> tuple[ValidationIssue, ...]:
    return tuple(sorted(issues, key=lambda item: (item.path, item.code)))


def error(
    code: str,
    message: str,
    *,
    path: str = "/",
    expected: Any = None,
    actual: Any = None,
    issues: Iterable[ValidationIssue] = (),
) -> WorldGenError:
    supplied = tuple(issues)
    if not supplied:
        supplied = (issue(code, path, message, expected, actual),)
    return WorldGenError(safe_issue_text(code), safe_issue_text(message), issues=sort_issues(supplied))


def read_json(path: str | Path, *, require_canonical: bool = False) -> Any:
    source = Path(path)
    try:
        payload = source.read_text(encoding="utf-8")
        parsed = parse_strict_json(payload)
        if require_canonical and canonical_payload(parsed) != payload:
            raise ValueError("artifact is not canonical JSON")
        return parsed
    except WorldGenError:
        raise
    except _StrictJSONError as exc:
        raise error(exc.code, f"cannot parse JSON document {source.name}") from exc
    except (UnicodeError, OSError, ValueError, TypeError) as exc:
        raise error("INVALID_JSON", f"cannot read JSON document {source.name}") from exc


def write_json(path: str | Path, value: Any) -> None:
    try:
        Path(path).write_text(canonical_payload(value), encoding="utf-8")
    except (UnicodeError, OSError, TypeError, ValueError) as exc:
        raise error("PROJECTION_INTEGRITY_MISMATCH", "cannot write canonical projection artifact") from exc


def has_invalid_text_controls(value: str) -> bool:
    return any(unicodedata.category(character) in {"Cc", "Cs"} for character in value)
