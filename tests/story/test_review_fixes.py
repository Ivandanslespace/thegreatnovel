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
    backup = tmp_path / "requests-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            nonlocal replaced
            if not replaced:
                _replace_directory(story / "requests", backup, kind="directory")
                replaced = True
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert replaced is True
    assert not list((story / "requests").iterdir())
    assert not list(backup.iterdir())
    _assert_no_story_temp(story)


def test_turn_directory_replacement_fails_closed_and_keeps_pending_request(story_factory, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    original_factory = service_module._story_publication_guard
    replaced = False
    backup = tmp_path / "turns-original"

    def replacement_guard(view, directory_name):
        original_check = original_factory(view, directory_name)

        def check():
            nonlocal replaced
            if not replaced:
                _replace_directory(story / "turns", backup, kind="directory")
                replaced = True
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert replaced is True
    assert not list((story / "turns").iterdir())
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
                _replace_directory(story / "requests", backup, kind=kind)
                replaced = True
            original_check()

        return check

    monkeypatch.setattr(service_module, "_story_publication_guard", replacement_guard)
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_PUBLICATION_UNAVAILABLE"
    assert replaced is True


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
