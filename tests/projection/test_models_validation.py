from __future__ import annotations

import json

import pytest

from tgn.core.hashing import canonical_json
from tgn.projection import PROJECTION_DRAFT_LABEL_FIELDS, load_projection_draft, validate_projection_draft
from tgn.worldgen.models import WorldGenError


def test_projection_draft_accepts_unicode_and_returns_detached_model(valid_projection_draft):
    value = dict(valid_projection_draft)
    value["labels"] = dict(value["labels"])
    value["labels"]["phase_day"] = "Français العربية́ 😀 \u202b白昼"
    draft, issues = validate_projection_draft(value)
    assert issues == ()
    assert draft is not None
    value["labels"]["phase_day"] = "mutated"
    assert draft.labels["phase_day"] != "mutated"
    assert canonical_json(draft.to_dict()).encode("utf-8")


@pytest.mark.parametrize("field", ["runtime_ids", "rules", "world_facts", "private_knowledge"])
def test_projection_draft_rejects_runtime_authority_fields(valid_projection_draft, field):
    candidate = dict(valid_projection_draft)
    candidate[field] = {}
    _, issues = validate_projection_draft(candidate)
    assert any(item.code == "UNKNOWN_FIELD" and item.path == f"/{field}" for item in issues)


def test_projection_draft_rejects_missing_and_unknown_labels(valid_projection_draft):
    candidate = dict(valid_projection_draft)
    candidate["labels"] = dict(candidate["labels"])
    del candidate["labels"]["phase_day"]
    candidate["labels"]["effect"] = "not allowed"
    _, issues = validate_projection_draft(candidate)
    assert ("MISSING_FIELD", "/labels/phase_day") in [(item.code, item.path) for item in issues]
    assert ("UNKNOWN_FIELD", "/labels/effect") in [(item.code, item.path) for item in issues]


@pytest.mark.parametrize("label", ["\ud800", "\udfff", "\x00", "line\nfeed"])
def test_projection_draft_rejects_surrogate_and_control_text(valid_projection_draft, label):
    candidate = dict(valid_projection_draft)
    candidate["labels"] = dict(candidate["labels"])
    candidate["labels"]["phase_day"] = label
    _, issues = validate_projection_draft(candidate)
    issue = next(item for item in issues if item.path == "/labels/phase_day")
    assert issue.code == "INVALID_TEXT"
    assert canonical_json(issue.to_dict()).encode("utf-8")
    assert "invalid_code_points" in issue.actual or "control" in issue.message


def test_escaped_surrogate_draft_reports_invalid_text_and_safe_cli_payload(tmp_path, source_worldpack_hash):
    value = {
        "schema_version": 1,
        "source_worldpack_hash": source_worldpack_hash,
        "labels": {field: "valid" for field in PROJECTION_DRAFT_LABEL_FIELDS},
    }
    value["labels"]["phase_day"] = "\ud800"
    path = tmp_path / "projection_draft.json"
    path.write_text(
        json.dumps(value, ensure_ascii=True, separators=(",", ":")),
        encoding="utf-8",
    )
    with pytest.raises(WorldGenError) as raised:
        load_projection_draft(path)
    assert raised.value.code == "INVALID_PROJECTION_DRAFT"
    bad = next(item for item in raised.value.issues if item.path == "/labels/phase_day")
    assert bad.code == "INVALID_TEXT"
    assert canonical_json(raised.value.issues_dict()).encode("utf-8")


def test_projection_draft_is_strict_about_hash(valid_projection_draft):
    candidate = dict(valid_projection_draft)
    candidate["source_worldpack_hash"] = "A" * 64
    _, issues = validate_projection_draft(candidate)
    assert any(item.code == "INVALID_WORLD_PACK_HASH" for item in issues)


@pytest.mark.parametrize("value", [None, [], "draft"])
def test_projection_draft_requires_an_object(value):
    draft, issues = validate_projection_draft(value)
    assert draft is None
    assert issues[0].code == "INVALID_TYPE"
    assert issues[0].path == "/"


def test_projection_draft_reports_wrong_top_level_types(valid_projection_draft):
    candidate = dict(valid_projection_draft)
    candidate["schema_version"] = True
    candidate["labels"] = []
    _, issues = validate_projection_draft(candidate)
    assert any(item.path == "/schema_version" for item in issues)
    assert any(item.path == "/labels" and item.code == "INVALID_TYPE" for item in issues)


def test_projection_draft_reports_wrong_label_types_and_empty_text(valid_projection_draft):
    candidate = dict(valid_projection_draft)
    candidate["labels"] = dict(candidate["labels"])
    candidate["labels"]["phase_day"] = 1
    candidate["labels"]["phase_night"] = "   "
    _, issues = validate_projection_draft(candidate)
    assert any(item.path == "/labels/phase_day" and item.code == "INVALID_TYPE" for item in issues)
    assert any(item.path == "/labels/phase_night" and item.code == "INVALID_TEXT" for item in issues)
