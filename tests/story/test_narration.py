from __future__ import annotations

import pytest

from tgn.story import NarrationError, NarrationResponse, build_narration_request, fallback_response, validate_narration_response


def _request():
    events = [{"event_id": "e-1", "facts": [{"fact_id": "f-1", "text": "门已打开", "visibility": "public", "kind": "state", "source": "engine"}]}]
    return build_narration_request("demo", 1, events, {"seen": True}, {"arc": "opening"})


def test_request_hash_and_fallback_are_deterministic() -> None:
    request = _request()
    assert request.request_id.startswith("nr-")
    result = fallback_response(request)
    assert validate_narration_response(request, result).prose == "门已打开。"


def test_strict_claims_reject_extra_or_altered_fact() -> None:
    request = _request()
    response = fallback_response(request).to_dict()
    response["claims"] = list(response["claims"]) + [{"fact_id": "extra", "text": "凭空事实"}]
    with pytest.raises(NarrationError):
        validate_narration_response(request, response)
    response = fallback_response(request).to_dict()
    response["claims"][0]["text"] = "改写事实"
    with pytest.raises(NarrationError):
        validate_narration_response(request, response)


def test_hidden_facts_never_become_required_claims() -> None:
    request = build_narration_request("demo", 1, [{"event_id": "e-1", "facts": [{"fact_id": "secret", "text": "秘密", "visibility": "hidden", "kind": "secret", "source": "engine"}]}])
    assert request.required_claims == ()
    assert "没有新的" in fallback_response(request).prose


def test_non_mapping_claim_and_locale_mismatch_rejected() -> None:
    request = _request()
    response = fallback_response(request).to_dict()
    response["claims"] = ["not-an-object"]
    with pytest.raises(NarrationError):
        validate_narration_response(request, response)
    response = fallback_response(request).to_dict()
    response["locale"] = "en-US"
    with pytest.raises(NarrationError):
        validate_narration_response(request, response)
