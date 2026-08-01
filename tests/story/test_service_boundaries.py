from __future__ import annotations

import dataclasses
from pathlib import Path
from types import SimpleNamespace

import pytest

import tgn.story.service as service_module
from tgn.campaign.models import CampaignError
from tgn.story import StoryError, commit_story, init_story, prepare_story
from tgn.story.campaign_snapshot import capture_campaign_snapshot
from tgn.story.common import canonical_bytes
from tgn.story.reconstruction import reconstruct_campaign
from tgn.story.verification import load_story_view

from .conftest import response_for
from .test_service import _choose


def _pending(story_factory, *, action_type: str = "DROP"):
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    if action_type == "SEARCH":
        _choose(campaign, "DROP")
        first_request = prepare_story(story, campaign_dir=campaign)["request"]
        commit_story(story, campaign_dir=campaign, response=response_for(first_request))
    _choose(campaign, action_type)
    request = prepare_story(story, campaign_dir=campaign)["request"]
    view = load_story_view(story)
    _manifest, snapshot = service_module._load_bound(view, campaign)
    history = reconstruct_campaign(view.manifest, snapshot)
    return campaign, story, request, view, snapshot, history


def test_service_error_mapping_and_path_gates(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert service_module._campaign_integrity("x").code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert service_module._map_campaign_error(CampaignError("CAMPAIGN_NOT_FOUND", "x")).code == "INVALID_STORY_INPUT"
    assert service_module._map_campaign_error(CampaignError("INVALID_CAMPAIGN_INPUT", "x")).code == "INVALID_STORY_INPUT"
    assert service_module._map_campaign_error(CampaignError("CAMPAIGN_PUBLICATION_UNAVAILABLE", "x")).code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert service_module._map_campaign_error(CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "x")).code == "CAMPAIGN_INTEGRITY_MISMATCH"

    with pytest.raises(StoryError) as error:
        service_module._path_gate(None, campaign, story_may_be_missing=False)
    assert error.value.code == "INVALID_STORY_INPUT"
    monkeypatch.setattr(service_module, "validate_story_campaign_separation", lambda *_args, **_kwargs: (_ for _ in ()).throw(TypeError("bad")))
    with pytest.raises(StoryError) as error:
        service_module._path_gate(story, campaign, story_may_be_missing=False)
    assert error.value.code == "INVALID_STORY_INPUT"

    monkeypatch.undo()
    monkeypatch.setattr(service_module, "validate_story_campaign_separation", lambda *_args, **_kwargs: (_ for _ in ()).throw(StoryError("INVALID_STORY_INPUT", "already mapped")))
    with pytest.raises(StoryError):
        service_module._path_gate(story, campaign, story_may_be_missing=False)

    monkeypatch.undo()
    monkeypatch.setattr(service_module, "verify_and_capture_campaign", lambda *_args: (_ for _ in ()).throw(OSError("candidate")))
    with pytest.raises(StoryError) as error:
        service_module._load_bound(load_story_view(story), campaign)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(service_module, "load_story_view", lambda *_args: (_ for _ in ()).throw(TypeError("private")))
    with pytest.raises(StoryError) as error:
        service_module._load_story_and_bound(story, campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_stable_history_and_read_only_failure_mapping(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, request, view, snapshot, history = _pending(story_factory)
    monkeypatch.setattr(service_module, "reconstruct_campaign", lambda *_args: (_ for _ in ()).throw(RuntimeError("replay")))
    with pytest.raises(StoryError) as error:
        service_module._stable_history(view, campaign, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(service_module, "reconstruct_campaign", lambda *_args: history)
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: (_ for _ in ()).throw(OSError("changed")))
    with pytest.raises(StoryError) as error:
        service_module._stable_history(view, campaign, snapshot)
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"

    changed_files = list(snapshot.campaign_files)
    changed_files[0] = dataclasses.replace(changed_files[0], sha256="b" * 64)
    changed_snapshot = dataclasses.replace(snapshot, campaign_files=tuple(changed_files))
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: changed_snapshot)
    with pytest.raises(StoryError) as error:
        service_module._stable_history(view, campaign, snapshot)
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"

    bad_manifest = dataclasses.replace(snapshot, _file_bytes=tuple(
        (name, canonical_bytes({"bad": True}) if name == "campaign.json" else payload)
        for name, payload in snapshot._file_bytes
    ))
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: bad_manifest)
    with pytest.raises(StoryError) as error:
        service_module._stable_history(view, campaign, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(service_module, "load_story_view", lambda *_args: (_ for _ in ()).throw(RuntimeError("changed")))
    with pytest.raises(StoryError) as error:
        service_module._assert_story_read_only(view)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    monkeypatch.setattr(service_module, "reconstruct_campaign", lambda *_args: (_ for _ in ()).throw(StoryError("CAMPAIGN_INTEGRITY_MISMATCH", "already bounded")))
    with pytest.raises(StoryError) as error:
        service_module._stable_history(view, campaign, snapshot)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_publication_helper_error_mapping(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tgn.story.publication import PublicationConflict, PublicationRuntime, PublicationUnavailable

    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target"
    monkeypatch.setattr(service_module, "atomic_no_replace_move", lambda *_args, **_kwargs: (_ for _ in ()).throw(PublicationConflict("exists")))
    with pytest.raises(StoryError) as error:
        service_module._publish_directory(source, target)
    assert error.value.code == "STORY_ALREADY_EXISTS"
    for exception in (PublicationUnavailable("no"), PublicationRuntime("bad")):
        monkeypatch.setattr(service_module, "atomic_no_replace_move", lambda *_args, _exception=exception, **_kwargs: (_ for _ in ()).throw(_exception))
        with pytest.raises(StoryError) as error:
            service_module._publish_directory(source, target)
        assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"

    for exception in (PublicationConflict("exists"), PublicationUnavailable("no"), PublicationRuntime("bad")):
        monkeypatch.setattr(service_module, "publish_bytes_no_replace", lambda *_args, _exception=exception, **_kwargs: (_ for _ in ()).throw(_exception))
        with pytest.raises(StoryError) as error:
            service_module._publish_request(target, b"x")
        assert error.value.code in {"STORY_INTEGRITY_MISMATCH", "STORY_PUBLICATION_UNAVAILABLE"}

    assert service_module._resource_map({"salvage": "2"}) == {"salvage": 2}
    assert service_module._resource_map([{"resource_id": "salvage", "quantity": 2}, "bad"]) == {"salvage": 2}
    assert service_module._resource_map(None) == {}


def test_published_turn_and_owned_cleanup_boundaries(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _campaign, _story, request, _view, _snapshot, _history = _pending(story_factory)
    target = tmp_path / "turn.json"
    payload = b"payload"
    monkeypatch.setattr(service_module, "publish_bytes_no_replace", lambda *_args: (_ for _ in ()).throw(service_module.PublicationConflict("exists")))
    monkeypatch.setattr(service_module, "read_regular_file", lambda *_args: (payload, None))
    assert service_module._published_turn(target, payload) == "already_committed"
    monkeypatch.setattr(service_module, "read_regular_file", lambda *_args: (_ for _ in ()).throw(OSError("read")))
    assert service_module._published_turn(target, payload) == "conflict"
    monkeypatch.setattr(service_module, "publish_bytes_no_replace", lambda *_args: (_ for _ in ()).throw(service_module.PublicationRuntime("bad")))
    with pytest.raises(StoryError) as error:
        service_module._published_turn(target, payload)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"

    service_module._remove_owned_temp(None)

    owned = tmp_path / "owned"
    owned.mkdir()
    service_module._remove_owned_temp(owned)
    assert not owned.exists()
    missing = tmp_path / "missing"
    service_module._remove_owned_temp(missing)
    file_path = tmp_path / "file"
    file_path.write_bytes(b"x")
    with pytest.raises(StoryError) as error:
        service_module._remove_owned_temp(file_path)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"


def test_prose_context_and_response_parser_boundaries(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    _campaign, _story, request, _view, _snapshot, _history = _pending(story_factory, action_type="SEARCH")
    context = service_module._prose_context(type("Request", (), {"public_brief": request["public_brief"], "claim_requirements": request["claim_requirements"], "action_type": request["action_type"], "accepted_decision_number": request["accepted_decision_number"], "voice_id": request["voice_id"], "narration_locale": request["narration_locale"]})())
    assert context.action_type == "SEARCH"
    with pytest.raises(StoryError):
        service_module._validate_prose_guard(type("Request", (), {"public_brief": request["public_brief"], "claim_requirements": request["claim_requirements"], "action_type": request["action_type"], "accepted_decision_number": request["accepted_decision_number"]})(), "")
    monkeypatch.setattr(service_module, "validate_narration", lambda *_args: (_ for _ in ()).throw(service_module.NarrationValidationError("bad")))
    with pytest.raises(StoryError):
        service_module._validate_prose_guard(type("Request", (), {"public_brief": request["public_brief"], "claim_requirements": request["claim_requirements"], "action_type": request["action_type"], "accepted_decision_number": request["accepted_decision_number"]})(), "ok")

    with pytest.raises(StoryError):
        service_module._response_value("{bad")
    with pytest.raises(StoryError):
        service_module._response_value({"bad": True})
    for value in (None, "turn-x", "turn-000000", "turn-000001x"):
        with pytest.raises(StoryError):
            service_module._parse_turn_id(value)
    with pytest.raises(StoryError):
        service_module.StoryService(None)


def test_init_overlap_and_publication_failure_boundaries(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    with pytest.raises(StoryError) as error:
        init_story(campaign, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "INVALID_STORY_INPUT"

    target = story
    monkeypatch.setattr(service_module.os, "lstat", lambda *_args: (_ for _ in ()).throw(OSError("inspect")))
    with pytest.raises(StoryError) as error:
        init_story(target, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "INVALID_STORY_INPUT"


def test_existing_artifact_validation_and_prefix_boundaries(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, request, view, snapshot, history = _pending(story_factory)
    gap_view = dataclasses.replace(view, requests=((2, view.requests[0][1], view.requests[0][2]),))
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(gap_view, history)
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(view, dataclasses.replace(history, accepted_decisions=0))
    pending_view = dataclasses.replace(
        view,
        requests=((1, view.requests[0][1], view.requests[0][2]), (2, view.requests[0][1], view.requests[0][2])),
    )
    pending_history = dataclasses.replace(history, accepted_decisions=2, action_turns=(history.action_turns[0], history.action_turns[0]))
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(pending_view, pending_history)
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(view, dataclasses.replace(history, action_turns=(), accepted_decisions=0))

    commit_story(story, campaign_dir=campaign, response=response_for(request))
    committed_view = load_story_view(story)
    _manifest, committed_snapshot = service_module._load_bound(committed_view, campaign)
    committed_history = reconstruct_campaign(committed_view.manifest, committed_snapshot)
    committed_turn = committed_view.turns[0][1]
    bad_shared = dataclasses.replace(committed_turn, action_type="SEARCH")
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(dataclasses.replace(committed_view, turns=((1, bad_shared, committed_view.turns[0][2]),)), committed_history)
    bad_claims = dataclasses.replace(committed_turn, claims=[])
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(dataclasses.replace(committed_view, turns=((1, bad_claims, committed_view.turns[0][2]),)), committed_history)
    bad_prose = dataclasses.replace(committed_turn, prose="")
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(dataclasses.replace(committed_view, turns=((1, bad_prose, committed_view.turns[0][2]),)), committed_history)
    bad_hash = dataclasses.replace(committed_turn, turn_artifact_hash="b" * 64)
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(dataclasses.replace(committed_view, turns=((1, bad_hash, committed_view.turns[0][2]),)), committed_history)

    monkeypatch.setattr(service_module, "load_story_view", lambda *_args: dataclasses.replace(view, files=()))
    with pytest.raises(StoryError):
        service_module._assert_story_read_only(view)

    request_model = __import__("tgn.story.models", fromlist=["NarrationRequest"]).NarrationRequest.from_dict(request)
    monkeypatch.undo()
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: (_ for _ in ()).throw(OSError("changed")))
    with pytest.raises(StoryError) as error:
        service_module._commit_prefix_check(campaign, snapshot, request_model)
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"
    changed_files = list(snapshot.campaign_files)
    changed_files[0] = dataclasses.replace(changed_files[0], sha256="b" * 64)
    changed_snapshot = dataclasses.replace(snapshot, campaign_files=tuple(changed_files))
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: changed_snapshot)
    with pytest.raises(StoryError) as error:
        service_module._commit_prefix_check(campaign, snapshot, request_model)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"


def test_commit_rechecks_pending_request_at_publication_boundary(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, request, _view, _snapshot, _history = _pending(story_factory)
    original = service_module._commit_prefix_check

    def mutate_request(*args, **kwargs):
        original(*args, **kwargs)
        changed = dict(request)
        changed["choice_id"] = "tampered-choice"
        (story / "requests" / "turn-000001.json").write_bytes(canonical_bytes(changed))

    monkeypatch.setattr(service_module, "_commit_prefix_check", mutate_request)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert not list((story / "turns").iterdir())


def test_publication_boundary_error_mapping_and_binding_guards(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tgn.story.publication import PublicationBoundaryChanged

    campaign, story, request, view, _snapshot, _history = _pending(story_factory)
    target = tmp_path / "artifact.json"
    boundary_messages = {
        "Campaign snapshot changed": "CAMPAIGN_SNAPSHOT_CHANGED",
        "story-error:CAMPAIGN_SNAPSHOT_CHANGED": "CAMPAIGN_SNAPSHOT_CHANGED",
        "story-error:CAMPAIGN_INTEGRITY_MISMATCH": "CAMPAIGN_INTEGRITY_MISMATCH",
        "story-error:STORY_INTEGRITY_MISMATCH": "STORY_INTEGRITY_MISMATCH",
        "unclassified boundary": "STORY_PUBLICATION_UNAVAILABLE",
    }
    for message, expected_code in boundary_messages.items():
        monkeypatch.setattr(
            service_module,
            "publish_bytes_no_replace",
            lambda *_args, _message=message, **_kwargs: (_ for _ in ()).throw(PublicationBoundaryChanged(_message)),
        )
        with pytest.raises(StoryError) as error:
            service_module._publish_request(target, b"x")
        assert error.value.code == expected_code

        monkeypatch.setattr(
            service_module,
            "publish_bytes_no_replace",
            lambda *_args, _message=message, **_kwargs: (_ for _ in ()).throw(PublicationBoundaryChanged(_message)),
        )
        with pytest.raises(StoryError) as error:
            service_module._published_turn(target, b"x")
        assert error.value.code == expected_code

    with pytest.raises(ValueError):
        service_module._story_publication_guard(view, "invalid")
    with pytest.raises(ValueError):
        service_module._open_story_publication_bindings(view, "invalid")

    # A real parent-binding mismatch is a publication error rather than a
    # path-based fallback to another Story directory.
    binding = service_module.BoundPublicationDirectory.bind(tmp_path)
    try:
        with pytest.raises(service_module.PublicationRuntime):
            service_module.publish_bytes_no_replace(
                story / "requests" / "outside.json",
                b"x",
                parent_binding=binding,
            )
    finally:
        binding.close_safely()


def test_prepare_competing_identical_request_and_explicit_boundaries(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")

    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign, turn_id="turn-000001")
    assert error.value.code == "NARRATION_REQUEST_NOT_FOUND"

    _choose(campaign, "DROP")
    expected = service_module.reconstruct_campaign(
        load_story_view(story).manifest,
        service_module._load_bound(load_story_view(story), campaign)[1],
    ).action_turns[0].request.to_dict()

    original_publish = service_module._publish_request

    def competing_publish(path, payload, **kwargs):
        path.write_bytes(payload)
        raise StoryError("STORY_INTEGRITY_MISMATCH", "competing prepare won")

    monkeypatch.setattr(service_module, "_publish_request", competing_publish)
    prepared = prepare_story(story, campaign_dir=campaign)
    assert prepared["request"] == expected
    assert prepared["committed"] is False
    monkeypatch.setattr(service_module, "_publish_request", original_publish)

    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign, turn_id="turn-000002")
    assert error.value.code == "NARRATION_REQUEST_NOT_FOUND"


def test_service_write_and_commit_exception_boundaries(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    existing = tmp_path / "existing.json"
    existing.write_bytes(b"x")
    with pytest.raises(StoryError) as error:
        service_module._write_owned_file(existing, b"new")
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    target = tmp_path / "new.json"
    monkeypatch.setattr(service_module, "write_fd_all", lambda *_args: (_ for _ in ()).throw(OSError("write")))
    with pytest.raises(StoryError) as error:
        service_module._write_owned_file(target, b"payload")
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert target.exists()
    target.unlink()
    monkeypatch.undo()

    campaign, story, request, _view, _snapshot, _history = _pending(story_factory)
    monkeypatch.setattr(service_module, "reconstruct_campaign", lambda *_args: (_ for _ in ()).throw(StoryError("CAMPAIGN_INTEGRITY_MISMATCH", "replay")))
    with pytest.raises(StoryError) as error:
        service_module.commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    committed = service_module.commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert committed["result"] == "committed"
    monkeypatch.setattr(service_module, "read_regular_file", lambda *_args: (_ for _ in ()).throw(OSError("late read")))
    with pytest.raises(StoryError) as error:
        service_module.commit_story(story, campaign_dir=campaign, response=response_for(request, prose="another consequence."))
    assert error.value.code == "TURN_CONFLICT"


def test_commit_publication_conflict_result_is_bounded(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, request, _view, _snapshot, _history = _pending(story_factory)
    monkeypatch.setattr(service_module, "_published_turn", lambda *_args, **_kwargs: "conflict")
    with pytest.raises(StoryError) as error:
        service_module.commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "TURN_CONFLICT"
    assert not list((story / "turns").iterdir())


def test_service_guard_and_binding_failure_boundaries(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, request, view, snapshot, history = _pending(story_factory)

    with monkeypatch.context() as context:
        context.setattr(service_module, "story_directory_identity_matches", lambda *_args: False)
        with pytest.raises(service_module.PublicationRuntime):
            service_module._story_publication_guard(view, "requests")()
    with monkeypatch.context() as context:
        calls = iter([True, False])
        context.setattr(service_module, "story_directory_identity_matches", lambda *_args: next(calls))
        with pytest.raises(service_module.PublicationRuntime):
            service_module._story_publication_guard(view, "requests")()

    with monkeypatch.context() as context:
        context.setattr(
            service_module,
            "_require_complete_snapshot_unchanged",
            lambda *_args: (_ for _ in ()).throw(StoryError("STORY_INTEGRITY_MISMATCH", "story changed")),
        )
        with pytest.raises(StoryError) as error:
            service_module._prepare_publication_guard(view, campaign, snapshot)()
        assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    request_model = service_module.NarrationRequest.from_dict(request)
    with monkeypatch.context() as context:
        context.setattr(
            service_module.BoundPublicationDirectory,
            "read_child_bytes",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read")),
        )
        request_binding = service_module.BoundPublicationDirectory.bind(story / "requests")
        try:
            with pytest.raises(service_module.PublicationBoundaryChanged) as error:
                service_module._pending_request_unchanged(view, request_model, request_binding)
            assert str(error.value) == "story-error:STORY_INTEGRITY_MISMATCH"
        finally:
            request_binding.close_safely()

    missing_request_view = dataclasses.replace(
        view,
        requests=(),
        files=tuple(item for item in view.files if not item.relative_path.startswith("requests/")),
    )
    request_binding = service_module.BoundPublicationDirectory.bind(story / "requests")
    try:
        with pytest.raises(service_module.PublicationBoundaryChanged):
            service_module._pending_request_unchanged(missing_request_view, request_model, request_binding)
        different_request = dataclasses.replace(request_model, choice_id="different-choice")
        with pytest.raises(service_module.PublicationBoundaryChanged):
            service_module._pending_request_unchanged(view, different_request, request_binding)
    finally:
        request_binding.close_safely()

    original_bind = service_module.BoundPublicationDirectory.bind
    calls = {"count": 0}

    def bind_root_then_fail(path):
        calls["count"] += 1
        if calls["count"] == 1:
            return original_bind(path)
        raise service_module.PublicationRuntime("child bind")

    monkeypatch.setattr(service_module.BoundPublicationDirectory, "bind", classmethod(lambda cls, path: bind_root_then_fail(path)))
    with pytest.raises(StoryError) as error:
        service_module._open_story_publication_bindings(view, "requests")
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"

    monkeypatch.undo()
    source = tmp_path / "source-directory"
    source.mkdir()
    parent_binding = service_module.BoundPublicationDirectory.bind(tmp_path)
    try:
        service_module._publish_directory(source, tmp_path / "published-directory", parent_binding=parent_binding)
        assert (tmp_path / "published-directory").is_dir()
    finally:
        parent_binding.close_safely()

    missing = tmp_path / "missing-owned"
    with monkeypatch.context() as context:
        context.setattr(service_module.os.path, "lexists", lambda *_args: True)
        context.setattr(service_module.BoundPublicationDirectory, "bind", classmethod(lambda cls, *_args: (_ for _ in ()).throw(FileNotFoundError())))
        service_module._remove_owned_temp(missing)

    with monkeypatch.context() as context:
        context.setattr(service_module, "load_story_view", lambda *_args: (_ for _ in ()).throw(StoryError("STORY_INTEGRITY_MISMATCH", "already mapped")))
        with pytest.raises(StoryError) as error:
            service_module._assert_story_read_only(view)
        assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    # Verify the two artifact validation exits that protect against a Story
    # request or committed turn exceeding the reconstructed Campaign history.
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(
            dataclasses.replace(view, requests=((2, view.requests[0][1], view.requests[0][2]),)),
            history,
        )
    with pytest.raises(StoryError):
        service_module._validate_existing_artifacts(
            dataclasses.replace(view, requests=(), turns=((1, request_model, canonical_bytes(request)),)),
            history,
        )


def test_service_init_and_commit_failure_mapping(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="init-failures")
    manifest, snapshot = service_module.verify_and_capture_campaign(campaign)
    monkeypatch.setattr(service_module, "verify_and_capture_campaign", lambda *_args: (_ for _ in ()).throw(CampaignError("CAMPAIGN_INTEGRITY_MISMATCH", "bad")))
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.setattr(service_module, "verify_and_capture_campaign", lambda *_args: (_ for _ in ()).throw(RuntimeError("bad")))
    with pytest.raises(StoryError) as error:
        init_story(story_factory(name="init-failures-generic")[1], campaign_dir=story_factory(name="init-failures-generic-campaign")[0], story_id="story-002", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    campaign, story, config = story_factory(name="capture-failure")
    real_manifest, real_snapshot = service_module.verify_and_capture_campaign(campaign)
    monkeypatch.setattr(service_module, "verify_and_capture_campaign", lambda *_args: (real_manifest, real_snapshot))
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: (_ for _ in ()).throw(OSError("changed")))
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"

    monkeypatch.undo()
    campaign, story, config = story_factory(name="generic-init-failure")
    real_manifest, real_snapshot = service_module.verify_and_capture_campaign(campaign)
    monkeypatch.setattr(service_module, "verify_and_capture_campaign", lambda *_args: (real_manifest, real_snapshot))
    changed = dataclasses.replace(real_snapshot, campaign_manifest_hash="f" * 64)
    monkeypatch.setattr(service_module, "capture_campaign_snapshot", lambda *_args: changed)
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"

    monkeypatch.undo()
    campaign, story, request, _view, _snapshot, _history = _pending(story_factory)
    monkeypatch.setattr(service_module, "reconstruct_campaign", lambda *_args: (_ for _ in ()).throw(RuntimeError("replay")))
    with pytest.raises(StoryError) as error:
        service_module.commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"

    monkeypatch.undo()
    bad_prefix = response_for(request)
    bad_prefix["narration_request_id"] = "other-story:turn-000001"
    with pytest.raises(StoryError) as error:
        service_module.commit_story(story, campaign_dir=campaign, response=bad_prefix)
    assert error.value.code == "NARRATION_RESPONSE_INVALID"

    monkeypatch.setattr(
        service_module.BoundPublicationDirectory,
        "read_child_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("pending read")),
    )
    with pytest.raises(StoryError) as error:
        service_module.commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
