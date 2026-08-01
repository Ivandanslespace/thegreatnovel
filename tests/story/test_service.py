from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tgn.campaign import choose_campaign, next_campaign, stop_campaign
from tgn.story import (
    StoryError,
    commit_story,
    init_story,
    prepare_story,
    status_story,
    verify_story,
)
from tgn.story.common import canonical_bytes

from .conftest import response_for


def _choose(campaign: Path, action_type: str) -> dict:
    current = next_campaign(campaign)
    choice = next(item for item in current["canonical_request"]["choices"] if item["action_type"] == action_type)
    return choose_campaign(
        campaign,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
        choice_id=choice["choice_id"],
    )


def test_init_prepare_commit_verify_and_idempotency(story_factory) -> None:
    campaign, story, config = story_factory()
    created = init_story(
        story,
        campaign_dir=campaign,
        story_id=config["story_id"],
        initial_narration_locale=config["locale"],
        initial_voice_id="cablecar_survival",
    )
    assert created["novel_status"] == "ABSENT"
    assert {path.name for path in story.iterdir()} == {"story.json", "requests", "turns"}
    assert str(campaign) not in story.joinpath("story.json").read_text(encoding="utf-8")

    _choose(campaign, "DROP")
    prepared = prepare_story(story, campaign_dir=campaign)
    request = prepared["request"]
    assert request["event_seq_start"] == request["event_seq_end"]
    assert prepare_story(story, campaign_dir=campaign)["request"] == request
    committed = commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert committed["result"] == "committed"
    duplicate = commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert duplicate["result"] == "already_committed"
    assert status_story(story, campaign_dir=campaign)["committed_prefix"] == 1
    assert verify_story(story, campaign_dir=campaign)["valid"] is True


def test_invalid_response_keeps_pending_and_locale_is_fixed(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="zh-CN", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    invalid = response_for(request, prose="")
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=invalid)
    assert error.value.code == "NARRATION_RESPONSE_INVALID"
    assert status_story(story, campaign_dir=campaign)["pending_turn_id"] == "turn-000001"
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign, narration_locale="ar")
    assert error.value.code == "INVALID_STORY_INPUT"


def test_stop_creates_no_story_turn(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    current = next_campaign(campaign)["canonical_request"]
    stop_campaign(campaign, request_fingerprint=current["request_fingerprint"])
    assert prepare_story(story, campaign_dir=campaign)["request"] is None
    result = verify_story(story, campaign_dir=campaign)
    assert result["valid"] is True
    assert not list((story / "requests").iterdir())
    assert not list((story / "turns").iterdir())


def test_story_can_lag_after_campaign_append_and_old_request_commits(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    _choose(campaign, "EXTRACT")
    commit_story(story, campaign_dir=campaign, response=response_for(request))
    status = status_story(story, campaign_dir=campaign)
    assert status["missing_request_turn_ids"] == ["turn-000002"]
    assert verify_story(story, campaign_dir=campaign)["valid"] is True


def test_wrong_valid_campaign_is_binding_mismatch(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    other = tmp_path / "other"
    shutil.copytree(campaign, other)
    (other / "campaign.json").write_text(
        (other / "campaign.json").read_text(encoding="utf-8").replace('"campaign_id":"campaign-001"', '"campaign_id":"other-001"'),
        encoding="utf-8",
    )
    with pytest.raises(StoryError) as error:
        status_story(story, campaign_dir=other)
    assert error.value.code in {"CAMPAIGN_BINDING_MISMATCH", "CAMPAIGN_INTEGRITY_MISMATCH"}


def test_novel_is_unsupported_and_not_deleted(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    novel = story / "novel.md"
    novel.write_text("future", encoding="utf-8")
    with pytest.raises(StoryError) as error:
        verify_story(story, campaign_dir=campaign)
    assert error.value.code == "UNSUPPORTED_STORY_FORMAT"
    assert novel.exists()


def test_cli_uses_explicit_locators_and_emits_json(story_factory, capsys) -> None:
    from tgn.story.__main__ import main

    campaign, story, config = story_factory()
    assert main([
        "init",
        "--story-dir",
        str(story),
        "--campaign-dir",
        str(campaign),
        "--story-id",
        config["story_id"],
        "--locale",
        "en",
        "--voice-id",
        "cablecar_survival",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert main(["status", "--story-dir", str(story), "--campaign-dir", str(campaign)]) == 0
    assert json.loads(capsys.readouterr().out)["novel_status"] == "ABSENT"


def test_init_input_boundaries_and_missing_story(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id="Bad ID", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "INVALID_STORY_INPUT"
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="fr", initial_voice_id="cablecar_survival")
    assert error.value.code == "INVALID_STORY_INPUT"
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="unknown_voice")
    assert error.value.code == "INVALID_STORY_INPUT"

    story.mkdir()
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "STORY_ALREADY_EXISTS"

    missing = tmp_path / "missing-story"
    with pytest.raises(StoryError) as error:
        status_story(missing, campaign_dir=campaign)
    assert error.value.code == "STORY_NOT_FOUND"
    with pytest.raises(StoryError) as error:
        init_story(tmp_path / "bad-campaign-story", campaign_dir=tmp_path / "missing-campaign", story_id="story-001", initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "INVALID_STORY_INPUT"


def test_init_rejects_symlink_target_when_supported(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    target = tmp_path / "real-story"
    target.mkdir()
    try:
        story.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlink creation unavailable on this platform")
    with pytest.raises(StoryError) as error:
        init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    assert error.value.code == "INVALID_STORY_INPUT"


def test_moved_campaign_is_reopened_only_by_explicit_locator(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="ar", initial_voice_id="jingxuan")
    moved = tmp_path / "moved-campaign"
    shutil.move(campaign, moved)
    assert status_story(story, campaign_dir=moved)["story"]["initial_narration_locale"] == "ar"
    assert str(moved) not in "".join(path.read_text(encoding="utf-8") for path in story.rglob("*.json"))


def test_valid_different_campaign_is_binding_mismatch(story_factory) -> None:
    campaign, story, config = story_factory(name="one")
    other, _other_story, _other_config = story_factory(name="two", story_id="story-002")
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    with pytest.raises(StoryError) as error:
        status_story(story, campaign_dir=other)
    assert error.value.code == "CAMPAIGN_BINDING_MISMATCH"


def test_prepare_status_and_turn_id_boundaries(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    empty = prepare_story(story, campaign_dir=campaign)
    assert empty["request"] is None
    assert empty["status"]["next_preparable_turn_id"] is None
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign, turn_id="turn-1")
    assert error.value.code == "INVALID_STORY_INPUT"

    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    with pytest.raises(StoryError) as error:
        prepare_story(story, campaign_dir=campaign, turn_id="turn-000002")
    assert error.value.code == "NARRATION_REQUEST_NOT_FOUND"
    assert prepare_story(story, campaign_dir=campaign, turn_id=request["turn_id"])["request"] == request
    commit_story(story, campaign_dir=campaign, response=response_for(request))
    assert prepare_story(story, campaign_dir=campaign, turn_id=request["turn_id"])["committed"] is True


def test_response_identity_claim_and_conflict_errors(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    invalid_responses = [
        {**response_for(request), "unknown": True},
        {**response_for(request), "narration_request_hash": "b" * 64},
        {**response_for(request), "locale": "ar"},
        {**response_for(request), "claims": []},
        {**response_for(request), "narration_request_id": "story-001:turn-000002"},
    ]
    for response in invalid_responses:
        with pytest.raises(StoryError) as error:
            commit_story(story, campaign_dir=campaign, response=response)
        assert error.value.code in {"NARRATION_RESPONSE_INVALID", "NARRATION_REQUEST_NOT_FOUND"}
    assert not list((story / "turns").iterdir())
    commit_story(story, campaign_dir=campaign, response=response_for(request))
    with pytest.raises(StoryError) as error:
        commit_story(story, campaign_dir=campaign, response=response_for(request, prose="A different consequence became visible."))
    assert error.value.code == "TURN_CONFLICT"


def test_request_and_turn_tamper_are_detected(story_factory) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    request_path = story / "requests" / "turn-000001.json"
    changed = dict(request)
    changed["choice_id"] = "choice-tampered"
    request_path.write_bytes(canonical_bytes(changed))
    with pytest.raises(StoryError) as error:
        verify_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"

    request_path.write_bytes(canonical_bytes(request))
    commit_story(story, campaign_dir=campaign, response=response_for(request))
    turn_path = story / "turns" / "turn-000001.json"
    turn = json.loads(turn_path.read_text(encoding="utf-8"))
    turn["prose"] = "Tampered after commit."
    turn_path.write_bytes(canonical_bytes(turn))
    with pytest.raises(StoryError) as error:
        status_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_story_extra_artifact_and_symlink_are_rejected(story_factory, tmp_path: Path) -> None:
    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    extra = story / "requests" / "extra.json"
    extra.write_text("{}", encoding="utf-8")
    with pytest.raises(StoryError) as error:
        verify_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"
    extra.unlink()

    target = tmp_path / "target.json"
    target.write_bytes(b"{}")
    link = story / "requests" / "turn-000001.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("file symlink creation unavailable on this platform")
    with pytest.raises(StoryError) as error:
        verify_story(story, campaign_dir=campaign)
    assert error.value.code == "STORY_INTEGRITY_MISMATCH"


def test_verify_is_read_only_and_cli_response_file_and_errors(story_factory, capsys, tmp_path: Path) -> None:
    from tgn.story.__main__ import main

    campaign, story, config = story_factory()
    init_story(story, campaign_dir=campaign, story_id=config["story_id"], initial_narration_locale="en", initial_voice_id="cablecar_survival")
    _choose(campaign, "DROP")
    request = prepare_story(story, campaign_dir=campaign)["request"]
    before_story = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in story.rglob("*") if path.is_file()}
    before_campaign = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in campaign.rglob("*") if path.is_file()}
    assert verify_story(story, campaign_dir=campaign)["verification"]["read_only"] is True
    after_story = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in story.rglob("*") if path.is_file()}
    after_campaign = {path: (path.stat().st_size, path.stat().st_mtime_ns) for path in campaign.rglob("*") if path.is_file()}
    assert before_story == after_story
    assert before_campaign == after_campaign

    response_path = tmp_path / "response.json"
    response_path.write_bytes(canonical_bytes(response_for(request)))
    assert main(["commit", "--story-dir", str(story), "--campaign-dir", str(campaign), "--response-file", str(response_path)]) == 0
    assert json.loads(capsys.readouterr().out)["result"] == "committed"
    assert main(["verify", "--story-dir", str(story), "--campaign-dir", str(campaign)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["commit", "--story-dir", str(story), "--campaign-dir", str(campaign)]) == 1
    error_output = json.loads(capsys.readouterr().out)
    assert error_output["error"]["code"] == "NARRATION_RESPONSE_INVALID"
    assert main(["status", "--story-dir", str(story)]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_STORY_INPUT"
