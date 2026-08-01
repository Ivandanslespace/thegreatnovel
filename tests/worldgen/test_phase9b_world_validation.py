from __future__ import annotations

import pytest

from tgn.core.hashing import canonical_json
from tgn.worldgen import (
    MECHANICS_PROFILE,
    WorldGenError,
    compile_world,
    parse_strict_json,
    validate_documents,
    validate_draft,
    validate_request,
)
from tgn.worldgen.compiler import _StrictJSONError

from .conftest import draft_payload, request_payload


def test_request_normalizes_text_but_does_not_interpret_rules():
    request, issues = validate_request(
        {"schema_version": 1, "prompt": "\r\n  if reward = 99 then win  \r"}
    )
    assert not issues
    assert request is not None
    assert request.prompt == "if reward = 99 then win"


def test_request_and_draft_reject_non_object_documents():
    request, request_issues = validate_request([])
    draft, draft_issues = validate_draft("not an object")

    assert request is None
    assert draft is None
    assert request_issues[0].code == "INVALID_SCHEMA"
    assert draft_issues[0].code == "INVALID_SCHEMA"


def test_validate_documents_returns_normalized_pair_for_valid_inputs():
    request, draft, issues = validate_documents(request_payload(), draft_payload())

    assert not issues
    assert request is not None
    assert draft is not None
    assert request.prompt == request_payload()["prompt"]
    assert draft.world_id == draft_payload()["world_id"]


@pytest.mark.parametrize("schema_version", [True, 1.0, 2])
def test_request_rejects_bool_float_and_unsupported_schema(schema_version):
    request, issues = validate_request(
        {"schema_version": schema_version, "prompt": "prompt"}
    )
    assert request is None
    assert issues
    assert issues[0].code in {"INVALID_TYPE", "UNSUPPORTED_SCHEMA_VERSION"}


@pytest.mark.parametrize("prompt", ["", "   ", "x" * 4001, "bad\x00prompt"])
def test_request_rejects_invalid_prompt(prompt):
    request, issues = validate_request({"schema_version": 1, "prompt": prompt})
    assert request is None
    assert any(issue.code == "INVALID_TEXT" for issue in issues)


def test_direct_request_surrogate_is_rejected_with_canonicalizable_issue():
    request, issues = validate_request(
        {"schema_version": 1, "prompt": chr(0xD800)}
    )

    assert request is None
    assert [(issue.code, issue.path) for issue in issues] == [
        ("INVALID_TEXT", "/prompt")
    ]
    assert issues[0].actual == {"invalid_code_points": ["U+D800"]}
    canonical_json(issues[0].to_dict()).encode("utf-8")


@pytest.mark.parametrize(
    ("field", "path", "surrogate"),
    [
        ("world_id", "/world_id", chr(0xD800)),
        ("content_locale", "/content_locale", chr(0xDFFF)),
        ("title", "/title", chr(0xD800)),
        ("premise", "/premise", chr(0xDFFF)),
        ("labels.target", "/labels/target", chr(0xD800)),
    ],
)
def test_direct_draft_surrogates_are_rejected_with_safe_issue_actual(
    field, path, surrogate
):
    draft = draft_payload()
    if field.startswith("labels."):
        draft["labels"][field.split(".", 1)[1]] = surrogate
    else:
        draft[field] = surrogate

    normalized, issues = validate_draft(draft)

    assert normalized is None
    issue = next(issue for issue in issues if issue.path == path)
    assert issue.code == "INVALID_TEXT"
    canonical_json(issue.to_dict()).encode("utf-8")


def test_seed_surrogate_is_rejected_before_hashing(sample_request, sample_draft):
    with pytest.raises(WorldGenError) as error:
        compile_world(sample_request, sample_draft, chr(0xDFFF))

    assert error.value.code == "INVALID_TEXT"
    assert error.value.issues[0].path == "/seed"
    canonical_json(error.value.issues_dict()).encode("utf-8")


def test_unknown_surrogate_field_is_safe_in_machine_issue_payload():
    _, issues = validate_request(
        {
            "schema_version": 1,
            "prompt": "valid",
            chr(0xD800): chr(0xDFFF),
        }
    )

    assert issues[0].code == "UNKNOWN_FIELD"
    canonical_json([issue.to_dict() for issue in issues]).encode("utf-8")


def test_combined_validation_prefixes_and_sorts_request_and_draft_paths(
    sample_request, sample_draft
):
    sample_request["schema_version"] = 2
    del sample_draft["labels"]["target"]

    _, _, issues = validate_documents(sample_request, sample_draft)

    assert [(issue.code, issue.path) for issue in issues] == [
        ("MISSING_FIELD", "/draft/labels/target"),
        ("UNSUPPORTED_SCHEMA_VERSION", "/request/schema_version"),
    ]


def test_valid_combining_emoji_and_rtl_formatting_text_remains_supported():
    draft = draft_payload(
        title="Cafe\u0301 🚀\u200f",
        premise="中文、français، والعربية مع RTL\u200f。",
    )
    draft["labels"]["base"] = "基地 🚀\u030f"

    normalized, issues = validate_draft(draft)

    assert not issues
    assert normalized is not None
    canonical_json(normalized.to_dict()).encode("utf-8")


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("prompt", 7, "INVALID_TYPE"),
        ("world_id", 7, "INVALID_TYPE"),
        ("content_locale", 7, "INVALID_TYPE"),
        ("title", 7, "INVALID_TYPE"),
        ("premise", 7, "INVALID_TYPE"),
    ],
)
def test_contract_rejects_non_text_fields(field, value, code):
    if field == "prompt":
        _, issues = validate_request({"schema_version": 1, "prompt": value})
    else:
        draft = draft_payload()
        draft[field] = value
        _, issues = validate_draft(draft)
    assert any(issue.path == f"/{field}" and issue.code == code for issue in issues)


@pytest.mark.parametrize("schema_version", [True, 1.0, 2])
def test_draft_rejects_invalid_or_unsupported_schema_version(schema_version):
    draft = draft_payload()
    draft["schema_version"] = schema_version
    normalized, issues = validate_draft(draft)
    assert normalized is None
    assert issues[0].path == "/schema_version"
    assert issues[0].code in {"INVALID_TYPE", "UNSUPPORTED_SCHEMA_VERSION"}


def test_draft_rejects_non_text_profile_and_non_object_labels():
    draft = draft_payload()
    draft["mechanics_profile"] = 7
    draft["labels"] = []
    normalized, issues = validate_draft(draft)

    assert normalized is None
    assert {issue.path for issue in issues} == {"/labels", "/mechanics_profile"}
    assert {issue.code for issue in issues} == {"INVALID_SCHEMA", "INVALID_TYPE"}


def test_multiline_premise_is_normalized_without_rejecting_newline():
    draft = draft_payload(premise=" first line\r\nsecond line ")
    normalized, issues = validate_draft(draft)

    assert not issues
    assert normalized is not None
    assert normalized.premise == "first line\nsecond line"


def test_draft_reports_missing_and_unknown_fields_in_stable_order():
    draft = draft_payload()
    del draft["labels"]["target"]
    draft["rules"] = {"reward": 99}
    normalized, issues = validate_draft(draft)
    assert normalized is None
    assert [(issue.code, issue.path) for issue in issues] == [
        ("MISSING_FIELD", "/labels/target"),
        ("UNKNOWN_FIELD", "/rules"),
    ]


def test_draft_rejects_extra_label_and_unsupported_profile_with_allowed_values():
    draft = draft_payload()
    draft["labels"]["rules"] = "not allowed"
    draft["mechanics_profile"] = "future_profile"
    normalized, issues = validate_draft(draft)
    assert normalized is None
    assert {issue.code for issue in issues} == {
        "UNKNOWN_FIELD",
        "UNSUPPORTED_MECHANICS_PROFILE",
    }
    profile_issue = next(
        issue for issue in issues if issue.code == "UNSUPPORTED_MECHANICS_PROFILE"
    )
    assert profile_issue.allowed_values == [MECHANICS_PROFILE]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("world_id", "Bad ID", "INVALID_STABLE_ID"),
        ("world_id", "", "INVALID_STABLE_ID"),
        ("content_locale", "ar_XX", "INVALID_LOCALE_TAG"),
        ("title", "\x01title", "INVALID_TEXT"),
        ("premise", "", "INVALID_TEXT"),
    ],
)
def test_draft_rejects_invalid_ids_locale_and_display_text(field, value, code):
    draft = draft_payload()
    if field in draft["labels"]:
        draft["labels"][field] = value
    else:
        draft[field] = value
    normalized, issues = validate_draft(draft)
    assert normalized is None
    assert any(issue.code == code for issue in issues)


def test_arabic_display_text_is_valid_utf8_content():
    draft = draft_payload(
        world_id="arabic-ice-world",
        locale="ar",
        title="مدينة الجليد",
        premise="قطار يعبر جليدا لا ينتهي.",
        labels={
            "base": "قطار النجاة",
            "target": "محطة جليدية",
            "resource": "نواة الطاقة",
            "hazard": "عاصفة بيضاء",
            "named_actor": "ميرا",
            "named_actor_role": "حارسة الصيانة",
            "named_actor_public_goal": "تحقيق في الإشارة الغامضة",
        },
    )
    normalized, issues = validate_draft(draft)
    assert not issues
    assert normalized is not None
    assert normalized.content_locale == "ar"
    assert normalized.title == "مدينة الجليد"


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"value":NaN}',
        '{"value":Infinity}',
        '{"value":-Infinity}',
    ],
)
def test_strict_json_rejects_duplicate_and_nonstandard_numbers(payload):
    with pytest.raises(_StrictJSONError):
        parse_strict_json(payload)


def test_strict_json_rejects_nonfinite_overflow_and_parses_json_arrays():
    with pytest.raises(_StrictJSONError) as overflow:
        parse_strict_json('{"value":1e999}')
    assert overflow.value.code == "NON_CANONICAL_JSON_VALUE"
    assert parse_strict_json("[1,2]") == [1, 2]


@pytest.mark.parametrize("payload", [None, "{not json}"])
def test_strict_json_rejects_non_text_and_malformed_payloads(payload):
    with pytest.raises(_StrictJSONError) as error:
        parse_strict_json(payload)
    assert error.value.code == "INVALID_JSON"


def test_request_and_draft_contracts_keep_exact_top_level_fields():
    request = request_payload()
    draft = draft_payload()
    request["extra"] = True
    draft["state"] = {}
    _, request_issues = validate_request(request)
    _, draft_issues = validate_draft(draft)
    assert [(issue.code, issue.path) for issue in request_issues] == [
        ("UNKNOWN_FIELD", "/extra")
    ]
    assert [(issue.code, issue.path) for issue in draft_issues] == [
        ("UNKNOWN_FIELD", "/state")
    ]
