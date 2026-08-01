"""Phase 8 RecordedDecision schema and mismatch tests."""

from __future__ import annotations

import json

import pytest

from tgn.gameplay.expedition import build_observation
from tgn.llm_player import (
    RecordedDecision,
    RecordedDecisionFormatError,
    RecordedDecisionMismatch,
    RecordedDecisionPolicy,
    build_llm_decision_request,
    export_recorded_decisions,
    import_recorded_decisions,
)

from tests.gameplay.phase75_helpers import make_phase75_state


def _action_record_for_initial_state() -> tuple[RecordedDecision, dict]:
    observation = build_observation(make_phase75_state())
    request = build_llm_decision_request(observation, 1)
    choice = next(choice for choice in request.choices if choice.action_type == "DROP")
    record = RecordedDecision(
        decision_number=1,
        request_fingerprint=request.request_fingerprint,
        outcome="ACTION",
        choice_id=choice.choice_id,
        action_type=choice.action_type,
        params=choice.params,
        raw_response=f'{{"choice_id":"{choice.choice_id}"}}',
    )
    return record, observation


def _replace_record(record: RecordedDecision, **changes) -> RecordedDecision:
    values = record.to_dict()
    values.update(changes)
    return RecordedDecision(**values)


def test_recorded_decision_export_import_is_strict_and_canonical():
    action_record, _ = _action_record_for_initial_state()
    stop_record = RecordedDecision(
        decision_number=2,
        request_fingerprint="next-fingerprint",
        outcome="STOP",
        choice_id=None,
        action_type=None,
        params={},
        raw_response='{"stop":true}',
    )

    payload = export_recorded_decisions((action_record, stop_record))
    assert payload == export_recorded_decisions(import_recorded_decisions(payload))
    imported = import_recorded_decisions(payload)
    assert imported == (action_record, stop_record)
    assert json.loads(payload)["schema_version"] == 1


def test_recorded_decision_params_are_observationally_immutable():
    record, _ = _action_record_for_initial_state()
    before = record.to_dict()
    params = record.params
    params["forged"] = True

    assert record.to_dict() == before
    assert "forged" not in record.params


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":2,"decisions":[]}',
        '{"schema_version":true,"decisions":[]}',
        '{"schema_version":1.0,"decisions":[]}',
        '{"schema_version":1,"decisions":[{"decision_number":2}]}',
        '{"schema_version":1,"decisions":[{"decision_number":1,"request_fingerprint":"x","outcome":"UNKNOWN","choice_id":null,"action_type":null,"params":{},"raw_response":""}]}',
        '{"schema_version":1,"decisions":[{"decision_number":1,"request_fingerprint":"x","outcome":"STOP","choice_id":"choice-001","action_type":null,"params":{},"raw_response":""}]}',
    ],
)
def test_recorded_decision_import_rejects_invalid_schema(payload):
    with pytest.raises(RecordedDecisionFormatError):
        import_recorded_decisions(payload)


def _record_kwargs(**overrides):
    values = {
        "decision_number": 1,
        "request_fingerprint": "fingerprint",
        "outcome": "ACTION",
        "choice_id": "choice-000",
        "action_type": "WAIT",
        "params": {},
        "raw_response": '{"choice_id":"choice-000"}',
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    "overrides",
    [
        {"decision_number": 0},
        {"request_fingerprint": ""},
        {"outcome": "UNKNOWN"},
        {"raw_response": None},
        {"choice_id": None},
        {"action_type": None},
        {"outcome": "STOP", "choice_id": "choice-000"},
        {"params": []},
    ],
)
def test_recorded_decision_model_rejects_invalid_fields(overrides):
    with pytest.raises(RecordedDecisionFormatError):
        RecordedDecision(**_record_kwargs(**overrides))


def test_export_rejects_invalid_record_objects_and_gaps():
    with pytest.raises(RecordedDecisionFormatError):
        export_recorded_decisions((object(),))
    record, _ = _action_record_for_initial_state()
    with pytest.raises(RecordedDecisionFormatError):
        export_recorded_decisions((_replace_record(record, decision_number=2),))


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "not-json",
        '{"schema_version":1,"decisions":{}}',
        '{"schema_version":1,"decisions":[{"decision_number":1,"request_fingerprint":"x","outcome":"ACTION","choice_id":"choice-000","action_type":"WAIT","params":[],"raw_response":""}]}',
        '{"schema_version":1,"schema_version":1,"decisions":[]}',
        '{"schema_version":NaN,"decisions":[]}',
    ],
)
def test_recorded_decision_import_rejects_invalid_json_and_record_shapes(payload):
    with pytest.raises(RecordedDecisionFormatError):
        import_recorded_decisions(payload)


def test_recorded_decision_rejects_non_finite_and_non_json_params_at_creation():
    for params in ({"x": float("inf")}, {"x": float("-inf")}, {"x": object()}):
        with pytest.raises(RecordedDecisionFormatError) as error:
            RecordedDecision(**_record_kwargs(params=params))
        assert error.value.code == "NON_CANONICAL_JSON"


def test_import_rejects_non_finite_number_before_record_construction():
    payload = (
        '{"schema_version":1,"decisions":['
        '{"decision_number":1,"request_fingerprint":"x",'
        '"outcome":"ACTION","choice_id":"choice-000",'
        '"action_type":"WAIT","params":{"x":1e999},'
        '"raw_response":""}]}'
    )
    with pytest.raises(RecordedDecisionFormatError) as error:
        import_recorded_decisions(payload)
    assert error.value.code == "NON_CANONICAL_JSON"


def test_replay_rejects_changed_visible_observation_before_execution():
    record, _ = _action_record_for_initial_state()
    replay_policy = RecordedDecisionPolicy((record,))
    changed_state = make_phase75_state()
    changed_state.data["player"]["stamina"] = 2

    with pytest.raises(RecordedDecisionMismatch) as error:
        replay_policy(build_observation(changed_state), 1, "replay-actor")

    assert error.value.code == "REQUEST_FINGERPRINT_MISMATCH"
    assert replay_policy._index == 0


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("choice_id", "choice-999", "UNKNOWN_RECORDED_CHOICE"),
        ("action_type", "FORGED_ACTION", "ACTION_TYPE_MISMATCH"),
        ("params", {"actor_id": "other"}, "PARAMS_MISMATCH"),
    ],
)
def test_replay_rejects_tampered_action_record(field, value, expected_code):
    record, observation = _action_record_for_initial_state()
    tampered = _replace_record(record, **{field: value})
    replay_policy = RecordedDecisionPolicy((tampered,))

    with pytest.raises(RecordedDecisionMismatch) as error:
        replay_policy(observation, 1, "replay-actor")

    assert error.value.code == expected_code
    assert replay_policy._index == 0


def test_replay_rejects_missing_stop_and_does_not_silently_degrade():
    record, observation = _action_record_for_initial_state()
    replay_policy = RecordedDecisionPolicy((record,))
    with pytest.raises(RecordedDecisionMismatch) as remaining_error:
        replay_policy.assert_consumed()
    assert remaining_error.value.code == "RECORDS_REMAIN"
    intent = replay_policy(observation, 1, "replay-actor")
    assert intent is not None
    with pytest.raises(RecordedDecisionMismatch) as error:
        replay_policy(observation, 2, "replay-actor")
    assert error.value.code == "RECORDS_EXHAUSTED"


def test_replay_rejects_decision_number_mismatch_before_fingerprint():
    record, observation = _action_record_for_initial_state()
    replay_policy = RecordedDecisionPolicy((record,))
    with pytest.raises(RecordedDecisionMismatch) as error:
        replay_policy(observation, 2, "replay-actor")
    assert error.value.code == "DECISION_NUMBER_MISMATCH"


def _stop_record(number: int) -> RecordedDecision:
    return RecordedDecision(
        decision_number=number,
        request_fingerprint=f"stop-{number}",
        outcome="STOP",
        choice_id=None,
        action_type=None,
        params={},
        raw_response='{"stop":true}',
    )


def test_recorded_sequences_have_single_terminal_stop_semantics():
    action, _ = _action_record_for_initial_state()
    action_two = _replace_record(action, decision_number=2)
    action_three = _replace_record(action, decision_number=3)
    stop_one = _stop_record(1)
    stop_two = _stop_record(2)

    for sequence in ((action, stop_two), (action,)):
        payload = export_recorded_decisions(sequence)
        assert import_recorded_decisions(payload) == sequence
        assert isinstance(RecordedDecisionPolicy(sequence), RecordedDecisionPolicy)

    invalid_sequences = [
        ((stop_one, action_two), "NON_TERMINAL_STOP"),
        ((stop_one, stop_two), "MULTIPLE_STOP_DECISIONS"),
        ((action, stop_two, action_three), "NON_TERMINAL_STOP"),
    ]
    for sequence, expected_code in invalid_sequences:
        with pytest.raises(RecordedDecisionFormatError) as export_error:
            export_recorded_decisions(sequence)
        assert export_error.value.code == expected_code

        payload = json.dumps(
            {
                "schema_version": 1,
                "decisions": [record.to_dict() for record in sequence],
            }
        )
        with pytest.raises(RecordedDecisionFormatError) as import_error:
            import_recorded_decisions(payload)
        assert import_error.value.code == expected_code

        with pytest.raises(RecordedDecisionFormatError) as policy_error:
            RecordedDecisionPolicy(sequence)
        assert policy_error.value.code == expected_code
