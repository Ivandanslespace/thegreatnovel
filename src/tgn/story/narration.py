"""Strict, deterministic boundary between committed facts and prose.

This module deliberately contains no LLM integration.  A narrator may produce a
response, but the response is accepted only when it is an exact rendering of the
facts requested by the engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from tgn.contracts import NarrationRequest
from tgn.hashing import sha256_json

MAX_PROSE_LENGTH = 20_000
SCHEMA_VERSION = "tgn.narration.v1"


class NarrationError(ValueError):
    """Raised when a narration request or response violates the contract."""


@dataclass(frozen=True, slots=True)
class NarrationResponse:
    schema_version: str
    request_id: str
    request_hash: str
    locale: str
    claims: tuple[dict[str, Any], ...]
    prose: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "NarrationResponse":
        expected = {"schema_version", "request_id", "request_hash", "locale", "claims", "prose"}
        if set(value) != expected:
            raise NarrationError("narration response fields must be exactly schema_version/request_id/request_hash/locale/claims/prose")
        claims = value["claims"]
        if isinstance(claims, (str, bytes)) or not isinstance(claims, Sequence):
            raise NarrationError("claims must be an array")
        if any(not isinstance(c, Mapping) for c in claims):
            raise NarrationError("every claim must be an object")
        return cls(
            schema_version=str(value["schema_version"]),
            request_id=str(value["request_id"]),
            request_hash=str(value["request_hash"]),
            locale=str(value["locale"]),
            claims=tuple(dict(c) for c in claims),
            prose=value["prose"] if isinstance(value["prose"], str) else "",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        return dict(value.to_dict())
    raise NarrationError("expected JSON object")


def _event_claims(events: Sequence[Any]) -> tuple[dict[str, Any], ...]:
    claims: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for raw_event in events:
        event = _as_dict(raw_event)
        for raw_fact in event.get("facts", ()):
            fact = _as_dict(raw_fact)
            visibility = str(fact.get("visibility", "public"))
            if visibility not in {"public", "player"}:
                continue
            fact_id = fact.get("fact_id")
            if not isinstance(fact_id, str) or not fact_id:
                raise NarrationError("committed public facts require fact_id")
            for required in ("text", "kind", "source"):
                if required not in fact:
                    raise NarrationError(f"committed fact requires {required}")
            if fact_id in seen:
                if seen[fact_id] != fact:
                    raise NarrationError(f"fact id {fact_id} has conflicting contents")
                continue
            seen[fact_id] = fact
            # Claims are copied, not paraphrased.  This makes the request itself
            # auditable and prevents prose from becoming a second state channel.
            claims.append(fact)
    return tuple(claims)


def build_narration_request(
    campaign_id: str,
    turn: int,
    committed_events: Sequence[Any],
    player_observation: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> NarrationRequest:
    events = tuple(_as_dict(event) for event in committed_events)
    event_ids = tuple(str(event["event_id"]) for event in events)
    claims = _event_claims(events)
    request_context = dict(context or {})
    request_context.setdefault("locale", "zh-CN")
    if player_observation is not None:
        request_context.setdefault("player_observation", dict(player_observation))
    base = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "turn": int(turn),
        "event_ids": event_ids,
        "required_claims": claims,
        "context": request_context,
    }
    # Derive a stable id first, then cover that id in the request hash.  Thus
    # every field except request_hash is authenticated, including request_id.
    request_id = "nr-" + sha256_json(base).removeprefix("sha256:")[:24]
    request_hash = sha256_json({**base, "request_id": request_id})
    return NarrationRequest(
        schema_version=SCHEMA_VERSION,
        request_id=request_id,
        campaign_id=campaign_id,
        turn=int(turn),
        event_ids=event_ids,
        required_claims=claims,
        context=request_context,
        request_hash=request_hash,
    )


def validate_narration_response(
    request: NarrationRequest | Mapping[str, Any],
    response: NarrationResponse | Mapping[str, Any],
) -> NarrationResponse:
    req = _as_dict(request)
    resp = response if isinstance(response, NarrationResponse) else NarrationResponse.from_mapping(response)
    if resp.schema_version != req["schema_version"] or resp.request_id != req["request_id"]:
        raise NarrationError("narration response does not identify the request")
    if resp.request_hash != req["request_hash"]:
        raise NarrationError("narration request hash mismatch")
    if not resp.locale or not isinstance(resp.locale, str):
        raise NarrationError("locale is required")
    expected_locale = str(req.get("context", {}).get("locale", "zh-CN"))
    if resp.locale != expected_locale:
        raise NarrationError("narration locale does not match request locale")
    if not resp.prose.strip() or len(resp.prose) > MAX_PROSE_LENGTH:
        raise NarrationError("prose must be non-empty and within the length limit")
    required = {str(c["fact_id"]): dict(c) for c in req.get("required_claims", ())}
    actual = {str(c.get("fact_id")): dict(c) for c in resp.claims if isinstance(c, Mapping) and c.get("fact_id")}
    if len(actual) != len(resp.claims):
        raise NarrationError("claims must contain one object per fact id")
    if set(actual) != set(required):
        raise NarrationError("claims must contain exactly the required fact ids")
    for fact_id, claim in actual.items():
        if claim != required[fact_id]:
            raise NarrationError(f"claim {fact_id} differs from the committed fact")
    return resp


def fallback_response(request: NarrationRequest | Mapping[str, Any]) -> NarrationResponse:
    req = _as_dict(request)
    claims = tuple(dict(c) for c in req.get("required_claims", ()))
    lines = [str(c.get("text", "")) for c in claims if str(c.get("text", "")).strip()]
    if not lines and isinstance(req.get("context"), Mapping) and req["context"].get("ending"):
        prose = "故事暂歇于已经提交的历史；没有未发生的胜利。"
    else:
        prose = "。".join(lines) + ("。" if lines else "这一回合没有新的可叙述事实。")
    return NarrationResponse(
        schema_version=str(req["schema_version"]),
        request_id=str(req["request_id"]),
        request_hash=str(req["request_hash"]),
        locale=str(req.get("context", {}).get("locale", "zh-CN")),
        claims=claims,
        prose=prose,
    )


def commit_narration(store: Any, response: NarrationResponse | Mapping[str, Any]) -> dict[str, Any]:
    """Delegate the atomic durable operation to CampaignStore.

    Keeping this tiny wrapper lets callers depend on the story boundary without
    giving the story layer a second persistence implementation.
    """

    return store.commit_narration(response)


def verify_story(store: Any) -> dict[str, Any]:
    """Verify the authoritative store and all story artifacts."""

    return store.verify()
