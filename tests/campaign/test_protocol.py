from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tgn.campaign import CampaignError, choose_campaign, next_campaign, stop_campaign, verify_campaign

from .conftest import choice_for, file_snapshot


def sqlite_authoritative_rows(root: Path) -> tuple[tuple, ...]:
    connection = sqlite3.connect(root / "session" / "campaign.sqlite3")
    try:
        campaigns = tuple(connection.execute("SELECT * FROM campaigns ORDER BY campaign_id"))
        events = tuple(connection.execute("SELECT * FROM events ORDER BY campaign_id, event_seq"))
        snapshots = tuple(connection.execute("SELECT * FROM snapshots ORDER BY campaign_id, event_seq, id"))
        return campaigns, events, snapshots
    finally:
        connection.close()


def expect_error(callable_obj, *args, **kwargs) -> CampaignError:
    with pytest.raises(CampaignError) as error:
        callable_obj(*args, **kwargs)
    return error.value


def test_next_and_choose_keep_request_and_presentation_separate(campaign_factory) -> None:
    target, created = campaign_factory()
    current = next_campaign(target)
    assert current["campaign"] == created["campaign"]
    assert current["canonical_request"] == created["canonical_request"]
    assert current["player_presentation"] == created["player_presentation"]

    drop = choice_for(current["canonical_request"], "DROP")
    chosen = choose_campaign(
        target,
        request_fingerprint=current["canonical_request"]["request_fingerprint"],
        choice_id=drop["choice_id"],
    )
    assert chosen["ok"] is True
    assert chosen["result"]["choice_id"] == drop["choice_id"]
    assert chosen["canonical_request"]["request_fingerprint"] == chosen["player_presentation"]["request_fingerprint"]
    assert chosen["canonical_request"]["choices"]
    assert "action_type" in chosen["canonical_request"]["choices"][0]
    assert "action_type" in chosen["player_presentation"]["choices"][0]


def test_stale_request_is_zero_side_effect(campaign_factory) -> None:
    target, created = campaign_factory()
    before_files = file_snapshot(target)
    before_rows = sqlite_authoritative_rows(target)
    error = expect_error(
        choose_campaign,
        target,
        request_fingerprint="b" * 64,
        choice_id=created["canonical_request"]["choices"][0]["choice_id"],
    )
    assert error.code == "STALE_REQUEST"
    assert file_snapshot(target) == before_files
    assert sqlite_authoritative_rows(target) == before_rows


def test_unknown_choice_is_zero_side_effect_and_has_no_display_fallback(campaign_factory) -> None:
    target, created = campaign_factory()
    before_files = file_snapshot(target)
    before_rows = sqlite_authoritative_rows(target)
    error = expect_error(
        choose_campaign,
        target,
        request_fingerprint=created["canonical_request"]["request_fingerprint"],
        choice_id="DROP",
    )
    assert error.code == "UNKNOWN_CHOICE"
    assert file_snapshot(target) == before_files
    assert sqlite_authoritative_rows(target) == before_rows


def test_engine_rejected_legal_choice_is_campaign_integrity_error(campaign_factory) -> None:
    target, created = campaign_factory()
    wait = choice_for(created["canonical_request"], "WAIT")
    before = file_snapshot(target)
    error = expect_error(
        choose_campaign,
        target,
        request_fingerprint=created["canonical_request"]["request_fingerprint"],
        choice_id=wait["choice_id"],
    )
    assert error.code == "CAMPAIGN_INTEGRITY_MISMATCH"
    assert file_snapshot(target) == before


def test_stop_is_terminal_and_creates_exactly_one_stop_record(campaign_factory) -> None:
    target, created = campaign_factory()
    fingerprint = created["canonical_request"]["request_fingerprint"]
    stopped = stop_campaign(target, request_fingerprint=fingerprint)
    assert stopped["session"]["status"] == "STOPPED"
    assert stopped["canonical_request"] is None
    assert stopped["player_presentation"] is None
    rows_before_repeat = sqlite_authoritative_rows(target)
    files_before_repeat = file_snapshot(target)
    error = expect_error(stop_campaign, target, request_fingerprint=fingerprint)
    assert error.code == "SESSION_TERMINAL"
    assert sqlite_authoritative_rows(target) == rows_before_repeat
    assert file_snapshot(target) == files_before_repeat
    decisions_bundle = __import__("json").loads(
        (target / "session" / "recorded_decisions.json").read_text(encoding="utf-8")
    )
    decisions = decisions_bundle["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["outcome"] == "STOP"
    assert sqlite_authoritative_rows(target)[1] == ()


def test_verify_returns_read_only_summary_and_terminal_nulls(campaign_factory) -> None:
    target, created = campaign_factory()
    before = file_snapshot(target)
    result = verify_campaign(target)
    assert result["verification"]["valid"] is True
    assert result["verification"]["recorded_decision_replay_completion_calls"] == 0
    assert result["canonical_request"] == created["canonical_request"]
    assert file_snapshot(target) == before

    stop_campaign(target, request_fingerprint=created["canonical_request"]["request_fingerprint"])
    terminal = verify_campaign(target)
    assert terminal["canonical_request"] is None
    assert terminal["player_presentation"] is None


def test_operations_only_accept_public_fingerprint_and_choice_id() -> None:
    import inspect

    from tgn.campaign import choose_campaign, stop_campaign

    assert set(inspect.signature(choose_campaign).parameters) == {
        "campaign_dir",
        "request_fingerprint",
        "choice_id",
    }
    assert set(inspect.signature(stop_campaign).parameters) == {
        "campaign_dir",
        "request_fingerprint",
    }
