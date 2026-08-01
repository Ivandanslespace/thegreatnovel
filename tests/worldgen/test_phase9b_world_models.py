from __future__ import annotations

from tgn.worldgen import COMPILER_ID, MECHANICS_PROFILE
from tgn.worldgen.models import (
    CompiledWorldPack,
    ValidationIssue,
    WorldDraft,
    WorldGenesisRequest,
    WorldGenError,
)


def test_edge_models_have_detached_canonical_shapes(sample_draft):
    request = WorldGenesisRequest(schema_version=1, prompt="prompt")
    assert request.to_dict() == {"schema_version": 1, "prompt": "prompt"}

    draft = WorldDraft(
        schema_version=1,
        mechanics_profile=MECHANICS_PROFILE,
        world_id=sample_draft["world_id"],
        content_locale=sample_draft["content_locale"],
        title=sample_draft["title"],
        premise=sample_draft["premise"],
        labels=sample_draft["labels"],
    )
    exported = draft.to_dict()
    exported["labels"]["base"] = "changed only in export"
    assert draft.labels["base"] == sample_draft["labels"]["base"]

    pack = CompiledWorldPack(
        schema_version=1,
        compiler_id=COMPILER_ID,
        mechanics_profile=MECHANICS_PROFILE,
        world_id="world",
        content_locale="en",
        public_content={"title": "Title", "premise": "Premise", "labels": {}},
        runtime_bindings={"base_location_id": "base-1"},
    )
    pack_dict = pack.to_dict()
    pack_dict["public_content"]["title"] = "mutated"
    assert pack.public_content["title"] == "Title"


def test_validation_issue_has_exact_machine_fields():
    issue = ValidationIssue(
        code="MISSING_FIELD",
        path="/labels/target",
        message="required field is missing",
        expected="non-empty string",
    )
    assert set(issue.to_dict()) == {
        "code",
        "path",
        "message",
        "expected",
        "actual",
        "allowed_values",
    }
    assert issue.to_dict()["actual"] is None


def test_worldgen_error_exports_stable_error_and_issue_payloads():
    issue = ValidationIssue(
        code="INVALID_SCHEMA",
        path="/prompt",
        message="prompt is invalid",
        actual={"secret": "detached"},
    )
    error = WorldGenError("INVALID_SCHEMA", "request is invalid", issues=(issue,))

    assert error.error_dict() == {
        "code": "INVALID_SCHEMA",
        "message": "request is invalid",
    }
    exported = error.issues_dict()
    exported[0]["actual"]["secret"] = "changed only in export"
    assert issue.actual == {"secret": "detached"}
