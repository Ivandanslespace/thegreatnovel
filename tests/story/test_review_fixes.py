from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import tgn.story.service as service_module
from tgn.campaign import next_campaign, stop_campaign, verify_campaign
from tgn.story import StoryError, commit_story, init_story, prepare_story, status_story, verify_story
from tgn.story.verification import load_story_view

from .conftest import response_for
from .test_service import _choose


def _replace_directory(path: Path, backup: Path, *, kind: str) -> Path:
    path.rename(backup)
    if kind == "directory":
        path.mkdir()
    elif kind == "file":
        path.write_bytes(b"replacement")
    elif kind == "symlink":
        target = backup.parent / f"{backup.name}-target"
        target.mkdir()
        path.symlink_to(target, target_is_directory=True)
    elif kind == "junction":
        target = backup.parent / f"{backup.name}-junction-target"
        target.mkdir()
        try:
            completed = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(path), str(target)],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"Windows junction creation is unavailable: {type(exc).__name__}")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "junction creation failed").strip()
            pytest.skip(f"Windows junction creation is unavailable: {detail[:120]}")
    else:
        raise AssertionError(f"unknown replacement kind: {kind}")
    return backup


def _assert_no_story_temp(path: Path) -> None:
    assert not [item for item in path.rglob("*") if ".tmp" in item.name or item.name.startswith(".")]


def _replace_or_report_blocked(path: Path, backup: Path, *, kind: str) -> bool:
    """Return True when a Windows parent HANDLE correctly blocks replacement."""

    try:
        _replace_directory(path, backup, kind=kind)
    except PermissionError:
        return True
    return False


def test_prepare_requires_complete_snapshot_at_publication_boundary(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")

    real_capture = service_module.capture_campaign_snapshot
    calls = 0

    def append_campaign_before_final_capture(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            _choose(campaign, "EXTRACT")
        return real_capture(path)

    monkeypatch.setattr(service_module, "capture_campaign_snapshot", append_campaign_before_final_capture)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"
    assert not list((story / "requests").iterdir())
    assert not list((story / "turns").iterdir())
    _assert_no_story_temp(story)


def test_prepare_rechecks_campaign_snapshot_inside_publication_boundary(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="prepare-publication-race")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    original_publish = service_module._publish_request
    appended = False

    def append_then_publish(path, payload, **kwargs):
        nonlocal appended
        if not appended:
            _choose(campaign, "EXTRACT")
            appended = True
        return original_publish(path, payload, **kwargs)

    monkeypatch.setattr(service_module, "_publish_request", append_then_publish)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "CAMPAIGN_SNAPSHOT_CHANGED"
    assert appended is True
    assert not list((story / "requests").iterdir())
    assert not list((story / "turns").iterdir())
    _assert_no_story_temp(story)


def test_prepare_existing_committed_request_is_read_only_with_later_pending(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    first = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(story, campaign_dir=campaign, response=response_for(first))
    _choose(campaign, "EXTRACT")
    second = prepare_story(story, campaign_dir=campaign)["request"]

    existing = prepare_story(story, campaign_dir=campaign, turn_id=first["turn_id"])
    assert existing["request"] == first
    assert existing["committed"] is True
    assert prepare_story(story, campaign_dir=campaign)["request"] == second


def test_recommit_rejects_same_bytes_with_new_committed_turn_identity(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="recommit-same-bytes-new-identity")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response = response_for(request)
    commit_story(story, campaign_dir=campaign, response=response)
    turn_path = story / "turns" / "turn-000001.json"
    original_payload = turn_path.read_bytes()
    original_load = service_module.load_story_view
    armed = True
    replaced = False

    def load_and_replace(path: Path):
        nonlocal replaced
        view = original_load(path)
        if armed and not replaced:
            before = next(item for item in view.files if item.relative_path == "turns/turn-000001.json")
            turn_path.unlink()
            turn_path.write_bytes(original_payload)
            after = next(item for item in original_load(path).files if item.relative_path == "turns/turn-000001.json")
            assert after.identity != before.identity
            replaced = True
        return view

    monkeypatch.setattr(service_module, "load_story_view", load_and_replace)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert replaced is True
    assert turn_path.read_bytes() == original_payload


def test_recommit_rejects_turn_directory_replacement_even_with_identical_turn(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="recommit-turn-directory-replacement")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response = response_for(request)
    commit_story(story, campaign_dir=campaign, response=response)
    turns = story / "turns"
    backup = tmp_path / "recommit-turns-original"
    original_load = service_module.load_story_view
    replaced = False

    def load_and_replace(path: Path):
        nonlocal replaced
        view = original_load(path)
        if not replaced:
            turns.rename(backup)
            turns.mkdir()
            (turns / "turn-000001.json").write_bytes((backup / "turn-000001.json").read_bytes())
            replaced = True
        return view

    monkeypatch.setattr(service_module, "load_story_view", load_and_replace)
    try:
        with pytest.raises(StoryError) as error:
            commit_story(story, campaign_dir=campaign, response=response)
        assert error.value.code == "STORY_INTEGRITY_MISMATCH"
        assert replaced is True
        assert (turns / "turn-000001.json").exists()
        assert (backup / "turn-000001.json").exists()
    finally:
        if turns.exists():
            (turns / "turn-000001.json").unlink(missing_ok=True)
            turns.rmdir()
        if backup.exists():
            backup.rename(turns)


def test_recommit_rejects_story_root_replacement(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="recommit-story-root-replacement")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response = response_for(request)
    commit_story(story, campaign_dir=campaign, response=response)
    backup = tmp_path / "recommit-story-original"
    original_load = service_module.load_story_view
    replaced = False

    def load_and_replace(path: Path):
        nonlocal replaced
        view = original_load(path)
        if not replaced:
            story.rename(backup)
            story.mkdir()
            (story / "requests").mkdir()
            (story / "turns").mkdir()
            for relative in (
                "story.json",
                "requests/turn-000001.json",
                "turns/turn-000001.json",
            ):
                replacement = story / relative
                replacement.write_bytes((backup / relative).read_bytes())
            replaced = True
        return view

    monkeypatch.setattr(service_module, "load_story_view", load_and_replace)
    try:
        with pytest.raises(StoryError) as error:
            commit_story(story, campaign_dir=campaign, response=response)
        assert error.value.code == "STORY_INTEGRITY_MISMATCH"
        assert replaced is True
        assert (story / "turns" / "turn-000001.json").exists()
    finally:
        if story.exists():
            for relative in (
                "story.json",
                "requests/turn-000001.json",
                "turns/turn-000001.json",
            ):
                (story / relative).unlink(missing_ok=True)
            (story / "requests").rmdir()
            (story / "turns").rmdir()
            story.rmdir()
        if backup.exists():
            backup.rename(story)


def test_story_parent_symlink_is_rejected_before_any_story_read(story_factory, tmp_path: Path) -> None:
    campaign, _story, config = story_factory()
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    real_story = real_parent / "story"
    init_story(real_story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(real_story, campaign_dir=campaign)["request"]

    symlink_parent = tmp_path / "symlink-parent"
    try:
        symlink_parent.symlink_to(real_parent, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlink creation unavailable on this platform: {type(exc).__name__}")
    aliased_story = symlink_parent / "story"

    with pytest.raises(StoryError) as error:
        load_story_view(aliased_story)
    assert error.value.code == "INVALID_STORY_INPUT"
    for operation in (
        lambda: status_story(aliased_story, campaign_dir=campaign),
        lambda: verify_story(aliased_story, campaign_dir=campaign),
        lambda: prepare_story(aliased_story, campaign_dir=campaign),
        lambda: commit_story(aliased_story, campaign_dir=campaign, response=response_for(request)),
    ):
        with pytest.raises(StoryError) as error:
            operation()
        assert error.value.code == "INVALID_STORY_INPUT"


def test_request_directory_replacement_fails_closed_without_publication(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    original_factory = service_module._story_publication_guard
    replaced = False
    blocked = False
    backup = tmp_path / "requests-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            nonlocal replaced
            nonlocal blocked
            if not replaced:
                blocked = _replace_or_report_blocked(story / "requests", backup, kind="directory")
                replaced = True
                if blocked:
                    raise service_module.PublicationBoundaryChanged("parent replacement blocked")
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert replaced is True
    assert not list((story / "requests").iterdir())
    if backup.exists():
        assert not list(backup.iterdir())
    _assert_no_story_temp(story)


def test_turn_directory_replacement_fails_closed_and_keeps_pending_request(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original_factory = service_module._story_publication_guard
    replaced = False
    blocked = False
    backup = tmp_path / "turns-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            nonlocal replaced
            nonlocal blocked
            if not replaced:
                blocked = _replace_or_report_blocked(story / "turns", backup, kind="directory")
                replaced = True
                if blocked:
                    raise service_module.PublicationBoundaryChanged("parent replacement blocked")
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert replaced is True
    assert not list((story / "turns").iterdir())
    if backup.exists():
        assert not list(backup.iterdir())
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000001"


@pytest.mark.parametrize("kind", ["file", "symlink", "junction"])
def test_request_directory_type_replacement_fails_closed(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    campaign, story, config = story_factory(name=f"replace-{kind}")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    original_factory = service_module._story_publication_guard
    replaced = False
    backup = tmp_path / f"requests-{kind}-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            nonlocal replaced
            if not replaced:
                blocked = _replace_or_report_blocked(story / "requests", backup, kind=kind)
                replaced = True
                if blocked:
                    raise service_module.PublicationBoundaryChanged("parent replacement blocked")
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert replaced is True


def _assert_publication_tree_clean(path: Path, artifact_name: str) -> None:
    if path.is_symlink() or not path.exists():
        return
    if path.is_dir():
        assert not (path / artifact_name).exists()
        assert not [item for item in path.iterdir() if ".tmp" in item.name or item.name.startswith(".")]


@pytest.mark.parametrize("checkpoint", [1, 2, 3])
@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "junction"])
def test_prepare_request_parent_is_anchored_at_every_checkpoint(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checkpoint: int,
    kind: str,
) -> None:
    campaign, story, config = story_factory(name=f"prepare-anchor-{checkpoint}-{kind}")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    original_factory = service_module._story_publication_guard
    state = {"calls": 0, "attempted": False, "blocked": False}
    backup = tmp_path / f"requests-anchor-{checkpoint}-{kind}-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            state["calls"] += 1
            if state["calls"] == checkpoint:
                state["attempted"] = True
                try:
                    _replace_directory(story / "requests", backup, kind=kind)
                except PermissionError:
                    state["blocked"] = True
                    raise service_module.PublicationBoundaryChanged("parent replacement blocked")
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert state["attempted"] is True
    assert state["calls"] >= checkpoint
    _assert_publication_tree_clean(story / "requests", "turn-000001.json")
    _assert_publication_tree_clean(backup, "turn-000001.json")
    assert not (story / "turns" / "turn-000001.json").exists()


@pytest.mark.parametrize("checkpoint", [1, 2, 3])
def test_commit_turn_parent_is_anchored_at_every_checkpoint(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checkpoint: int,
) -> None:
    campaign, story, config = story_factory(name=f"commit-anchor-{checkpoint}")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original_factory = service_module._story_publication_guard
    state = {"calls": 0, "attempted": False, "blocked": False}
    backup = tmp_path / f"turns-anchor-{checkpoint}-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            state["calls"] += 1
            if state["calls"] == checkpoint:
                state["attempted"] = True
                try:
                    _replace_directory(story / "turns", backup, kind="directory")
                except PermissionError:
                    state["blocked"] = True
                    raise service_module.PublicationBoundaryChanged("parent replacement blocked")
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert state["attempted"] is True
    assert state["calls"] >= checkpoint
    assert (story / "requests" / "turn-000001.json").exists()
    _assert_publication_tree_clean(story / "turns", "turn-000001.json")
    _assert_publication_tree_clean(backup, "turn-000001.json")


def test_init_story_parent_binding_fails_closed_at_final_atomic_window(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, _unused_story, config = story_factory(name="init-parent-anchor")
    story_parent = tmp_path / "story-parent"
    story_parent.mkdir()
    story = story_parent / "story"
    backup = tmp_path / "story-parent-original"
    original_publish = service_module._publish_directory
    attempted = False

    def replace_before_atomic():
        nonlocal attempted
        attempted = True
        try:
            story_parent.rename(backup)
            story_parent.mkdir()
        except PermissionError:
            raise service_module.PublicationBoundaryChanged("parent replacement blocked")

    def publish_with_race(source, target, **kwargs):
        kwargs["before_atomic"] = replace_before_atomic
        return original_publish(source, target, **kwargs)

    monkeypatch.setattr(service_module, "_publish_directory", publish_with_race)
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert attempted is True
    assert not story.exists()
    _assert_publication_tree_clean(story_parent, "story")
    _assert_publication_tree_clean(backup, "story")


@pytest.mark.parametrize("operation", ["prepare", "commit"])
def test_final_check_to_atomic_parent_replacement_never_publishes(
    story_factory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    campaign, story, config = story_factory(name=f"final-parent-race-{operation}")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = None
    if operation == "prepare":
        original_publish = service_module._publish_request
        directory_name = "requests"
    else:
        request = prepare_story(story, campaign_dir=campaign)["request"]
        original_publish = service_module._published_turn
        directory_name = "turns"
    backup = tmp_path / f"{directory_name}-final-original"
    attempted = False

    def replace_before_atomic():
        nonlocal attempted
        attempted = True
        try:
            _replace_directory(story / directory_name, backup, kind="directory")
        except PermissionError:
            raise service_module.PublicationBoundaryChanged("parent replacement blocked")

    if operation == "prepare":
        def publish_with_race(path, payload, **kwargs):
            kwargs["before_atomic"] = replace_before_atomic
            return original_publish(path, payload, **kwargs)

        monkeypatch.setattr(service_module, "_publish_request", publish_with_race)
        call = lambda: prepare_story(story, campaign_dir=campaign)
    else:
        def publish_with_race(path, payload, **kwargs):
            kwargs["before_atomic"] = replace_before_atomic
            return original_publish(path, payload, **kwargs)

        monkeypatch.setattr(service_module, "_published_turn", publish_with_race)
        call = lambda: commit_story(story, campaign_dir=campaign, response=response_for(request))

    with pytest.raises(StoryError) as error:
        call()
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert attempted is True
    assert not (story / directory_name / f"turn-000001.json").exists()
    _assert_publication_tree_clean(story / directory_name, "turn-000001.json")
    _assert_publication_tree_clean(backup, "turn-000001.json")
    if operation == "commit":
        assert (story / "requests" / "turn-000001.json").exists()


def _tamper_historical_event(campaign: Path) -> None:
    database = campaign / "session" / "campaign.sqlite3"
    connection = sqlite3.connect(database)
    try:
        row = connection.execute("SELECT campaign_id FROM events ORDER BY event_seq LIMIT 1").fetchone()
        assert row is not None
        connection.execute(
            "UPDATE events SET payload_json = ? WHERE campaign_id = ? AND event_seq = 1",
            (json.dumps({"publication_race": True}, separators=(",", ":")), row[0]),
        )
        connection.commit()
    finally:
        connection.close()


def test_recommit_rejects_historical_campaign_prefix_mutation(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="recommit-historical-prefix-tamper")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response = response_for(request)
    commit_story(story, campaign_dir=campaign, response=response)
    original = service_module._commit_prefix_check
    tampered = False

    def mutate_before_prefix_check(*args, **kwargs):
        nonlocal tampered
        if not tampered:
            _tamper_historical_event(campaign)
            tampered = True
        return original(*args, **kwargs)

    monkeypatch.setattr(service_module, "_commit_prefix_check", mutate_before_prefix_check)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response)
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert tampered is True
    assert (story / "turns" / "turn-000001.json").exists()


def test_recommit_allows_later_campaign_append_with_unchanged_prefix(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="recommit-later-campaign-append")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    response = response_for(request)
    commit_story(story, campaign_dir=campaign, response=response)
    original = service_module._commit_prefix_check
    appended = False

    def append_before_prefix_check(campaign_dir, before, current_request):
        nonlocal appended
        if not appended:
            _choose(campaign, "EXTRACT")
            appended = True
        return original(campaign_dir, before, current_request)

    monkeypatch.setattr(service_module, "_commit_prefix_check", append_before_prefix_check)
    result = commit_story(story, campaign_dir=campaign, response=response)
    assert result["ok"] is True
    assert result["result"] == "already_committed"
    assert appended is True


@pytest.mark.parametrize("guard_call", [3, 4])
def test_commit_revalidates_historical_prefix_after_temp_and_before_atomic(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
    guard_call: int,
) -> None:
    campaign, story, config = story_factory(name=f"commit-prefix-race-{guard_call}")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original = service_module._commit_prefix_check
    calls = 0

    def check_with_race(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == guard_call:
            _tamper_historical_event(campaign)
        return original(*args, **kwargs)

    monkeypatch.setattr(service_module, "_commit_prefix_check", check_with_race)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert not (story / "turns" / "turn-000001.json").exists()
    _assert_no_story_temp(story)


def test_commit_allows_later_campaign_append_after_last_guard(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="commit-later-append-race")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original = service_module._published_turn
    appended = False

    def append_before_atomic(path, payload, **kwargs):
        nonlocal appended

        def append():
            nonlocal appended
            if not appended:
                _choose(campaign, "EXTRACT")
                appended = True

        kwargs["before_atomic"] = append
        return original(path, payload, **kwargs)

    monkeypatch.setattr(service_module, "_published_turn", append_before_atomic)
    result = commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert result["ok"] is True
    assert appended is True
    assert (story / "turns" / "turn-000001.json").exists()


@pytest.mark.parametrize("guard_call", [3, 4])
def test_commit_revalidates_pending_request_after_temp_and_before_atomic(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
    guard_call: int,
) -> None:
    campaign, story, config = story_factory(name=f"commit-request-race-{guard_call}")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original = service_module._commit_prefix_check
    calls = 0

    def check_with_request_replacement(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == guard_call:
            changed = dict(request)
            changed["choice_id"] = "tampered-choice"
            (story / "requests" / "turn-000001.json").write_bytes(service_module.canonical_bytes(changed))
        return original(*args, **kwargs)

    monkeypatch.setattr(service_module, "_commit_prefix_check", check_with_request_replacement)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert not (story / "turns" / "turn-000001.json").exists()


def test_commit_revalidates_pending_request_after_final_hook(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="commit-request-final-hook")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original = service_module._published_turn

    def replace_request():
        changed = dict(request)
        changed["choice_id"] = "tampered-choice"
        (story / "requests" / "turn-000001.json").write_bytes(service_module.canonical_bytes(changed))

    def publish_with_race(path, payload, **kwargs):
        kwargs["before_atomic"] = replace_request
        return original(path, payload, **kwargs)

    monkeypatch.setattr(service_module, "_published_turn", publish_with_race)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    assert not (story / "turns" / "turn-000001.json").exists()


def test_campaign_backed_story_path_and_terminal_max_decisions(story_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory(name="product", max_decisions=1)
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")

    def no_completion(*_args, **_kwargs):
        raise AssertionError("Phase 9C1 must not invoke a completion")

    from tgn.llm_player import policy

    monkeypatch.setattr(policy.LLMPlayerPolicy, "__init__", no_completion)
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    terminal_claims = [claim for claim in request["claim_requirements"] if claim["kind"] == "terminal_reason"]
    assert terminal_claims == [{"kind": "terminal_reason", "value": {"reason": "MAX_DECISIONS"}}]
    assert next_campaign(campaign)["session"]["status"] == "MAX_DECISIONS"
    commit_story(story, campaign_dir=campaign, response=response_for(request))

    verified_campaign = verify_campaign(campaign)
    assert verified_campaign["verification"]["event_replay"] is True
    assert verified_campaign["verification"]["recorded_decision_replay"] is True
    assert verify_story(story, campaign_dir=campaign)["valid"] is True


def test_campaign_backed_talk_resume_stop_replay_and_public_knowledge_boundary(
    story_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign, story, config = story_factory(name="product-resume", max_decisions=10)
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")

    def no_completion(*_args, **_kwargs):
        raise AssertionError("Phase 9C1 must not invoke a completion")

    from tgn.llm_player import policy

    monkeypatch.setattr(policy.LLMPlayerPolicy, "__init__", no_completion)

    _choose(campaign, "DROP")
    drop_request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(story, campaign_dir=campaign, response=response_for(drop_request))

    _choose(campaign, "SEARCH")
    search_request = prepare_story(story, campaign_dir=campaign)["request"]
    reopened = status_story(story, campaign_dir=campaign)
    assert reopened["pending_turn_id"] == "turn-000002"
    assert prepare_story(story, campaign_dir=campaign)["request"] == search_request
    commit_story(story, campaign_dir=campaign, response=response_for(search_request))

    _choose(campaign, "EXTRACT")
    extract_request = prepare_story(story, campaign_dir=campaign)["request"]
    commit_story(story, campaign_dir=campaign, response=response_for(extract_request))

    _choose(campaign, "TALK_TO_ACTOR")
    talk_request = prepare_story(story, campaign_dir=campaign)["request"]
    assert talk_request["action_type"] == "TALK_TO_ACTOR"

    forbidden_keys = {"knowledge", "goal", "private_goal", "world_truth", "private_world_truth"}

    def walk_keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from walk_keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk_keys(child)

    assert not forbidden_keys.intersection(walk_keys(talk_request))
    fact_claims = [claim for claim in talk_request["claim_requirements"] if claim["kind"] == "public_fact_revealed"]
    trust_claims = [claim for claim in talk_request["claim_requirements"] if claim["kind"] == "relationship_public_change"]
    assert any(claim["value"] == {"fact_id": "site-1-condition", "value": "unstable"} for claim in fact_claims)
    assert trust_claims == [
        {
            "kind": "relationship_public_change",
            "value": {"actor_id": "mara", "relationship_id": "trust", "before": 0, "after": 1},
        }
    ]
    commit_story(story, campaign_dir=campaign, response=response_for(talk_request))

    current = next_campaign(campaign)
    stop_result = stop_campaign(
        campaign,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
    )
    assert stop_result["session"]["status"] == "STOPPED"
    assert prepare_story(story, campaign_dir=campaign)["request"] is None
    assert not list((story / "requests").glob("turn-000005.json"))
    assert not list((story / "turns").glob("turn-000005.json"))

    verified_campaign = verify_campaign(campaign)
    assert verified_campaign["verification"]["event_replay"] is True
    assert verified_campaign["verification"]["recorded_decision_replay"] is True
    connection = sqlite3.connect(campaign / "session" / "campaign.sqlite3")
    try:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4
    finally:
        connection.close()
    records = json.loads((campaign / "session" / "recorded_decisions.json").read_text(encoding="utf-8"))["decisions"]
    assert [record["outcome"] for record in records] == ["ACTION"] * 4 + ["STOP"]
    assert verify_story(story, campaign_dir=campaign)["valid"] is True


def test_no_legal_actions_is_not_fabricated_for_current_frozen_fixture(story_factory) -> None:
    campaign, story, config = story_factory(name="product-no-legal", max_decisions=10)
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")

    # The frozen first WorldPack exposes a legal WAIT outside encounters and
    # FLEE during an active encounter.  Follow its real public path and do not
    # manufacture a request for a terminal state that the fixture cannot reach.
    for action_type in ("DROP", "SEARCH", "EXTRACT", "TALK_TO_ACTOR"):
        current = next_campaign(campaign)
        assert current["session"]["status"] == "AWAITING_DECISION"
        _choose(campaign, action_type)
        assert next_campaign(campaign)["session"]["status"] != "NO_LEGAL_ACTIONS"
    assert prepare_story(story, campaign_dir=campaign)["request"] is not None
