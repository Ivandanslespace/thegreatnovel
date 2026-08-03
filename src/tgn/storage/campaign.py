"""SQLite campaign persistence with an append-only, hash-chained event log."""

from __future__ import annotations

import copy
import dataclasses
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

from tgn.contracts import EngineResolution, EventDraft
from tgn.hashing import canonical_json, sha256_json, sha256_text
from tgn.story.narration import (
    NarrationError,
    build_narration_request,
    validate_narration_response,
)

CAMPAIGN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
SCHEMA_VERSION = "tgn.storage.v1"
STATUSES = {"ACTIVE", "STOPPING", "STOPPED"}
_ALLOWED_BUSINESS_ROOTS = {"player", "actors", "world", "opportunities", "unlocks", "metrics"}


def _validate_business_state(state: Mapping[str, Any], campaign_id: str | None = None) -> None:
    """Validate the durable JSON state before it can enter the event chain."""
    if not isinstance(state, Mapping):
        raise IntegrityError("initial state must be an object")
    roots = set(state)
    missing = _ALLOWED_BUSINESS_ROOTS - roots
    if missing:
        raise IntegrityError(f"state is missing business roots: {sorted(missing)}")
    for root in ("player", "actors", "world", "opportunities", "metrics"):
        if not isinstance(state.get(root), Mapping):
            raise IntegrityError(f"state.{root} must be an object")
    if not isinstance(state.get("unlocks"), list):
        raise IntegrityError("state.unlocks must be an array")
    campaign = state.get("campaign")
    if not isinstance(campaign, Mapping):
        raise IntegrityError("state.campaign metadata is required")
    if campaign_id is not None and campaign.get("campaign_id") != campaign_id:
        raise IntegrityError("state campaign_id does not match campaign identity")
    for key in ("campaign_id",):
        if not isinstance(campaign.get(key), str) or not campaign[key]:
            raise IntegrityError(f"campaign.{key} must be a non-empty string")
    for key in ("turn", "time_minute", "current_tier"):
        value = campaign.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise IntegrityError(f"campaign.{key} must be a non-negative integer")
    if "status" in campaign and not isinstance(campaign["status"], str):
        raise IntegrityError("campaign.status must be a string")


def _validate_fact(fact: Mapping[str, Any], *, assigned: bool = False) -> None:
    if not isinstance(fact, Mapping):
        raise IntegrityError("fact must be an object")
    if assigned and "fact_id" in fact:
        raise IntegrityError("fact_id is assigned by storage")
    for key in ("text", "visibility", "kind", "source"):
        if key not in fact or not isinstance(fact[key], str) or not fact[key].strip():
            raise IntegrityError(f"fact.{key} must be a non-empty string")
    visibility = fact["visibility"]
    if not (visibility in {"public", "player", "hidden"} or (visibility.startswith("actor:") and visibility[6:].strip())):
        raise IntegrityError("invalid fact visibility")


class CampaignStoreError(RuntimeError):
    pass


class IntegrityError(CampaignStoreError):
    pass


class ReadOnlyCampaignError(CampaignStoreError):
    pass


class CommandConflict(CampaignStoreError):
    pass


def _json(value: Any) -> str:
    return canonical_json(value)


def _loads(value: str) -> Any:
    return json.loads(value)


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    return value


def _state_hash(state: Mapping[str, Any]) -> str:
    return sha256_json(state)


def _campaign_meta(state: Mapping[str, Any]) -> dict[str, Any]:
    campaign = state.get("campaign")
    if not isinstance(campaign, Mapping):
        raise IntegrityError("state.campaign metadata is required")
    return dict(campaign)


def _apply_event_state(state: Mapping[str, Any], patches: Iterable[Mapping[str, Any]], details: Mapping[str, Any]) -> dict[str, Any]:
    """Replay business patches, then apply engine-owned campaign metadata."""

    next_state = copy.deepcopy(dict(state))
    for patch in patches:
        next_state = apply_patch(next_state, patch)
    before = _campaign_meta(state)
    campaign = _campaign_meta(next_state)
    turn_after = details.get("turn_after", int(before.get("turn", 0)) + 1)
    time_after = details.get("time_after", int(before.get("time_minute", 0)))
    if not isinstance(turn_after, int) or isinstance(turn_after, bool) or turn_after < int(before.get("turn", 0)):
        raise IntegrityError("invalid event turn_after")
    if not isinstance(time_after, int) or isinstance(time_after, bool) or time_after < int(before.get("time_minute", 0)):
        raise IntegrityError("invalid event time_after")
    campaign["turn"] = turn_after
    campaign["time_minute"] = time_after
    if "tier_after" in details:
        campaign["current_tier"] = details["tier_after"]
    elif "current_tier" not in campaign and "current_tier" in before:
        campaign["current_tier"] = before["current_tier"]
    next_state["campaign"] = campaign
    world = next_state.get("world")
    if not isinstance(world, dict):
        raise IntegrityError("state.world must be an object")
    world["minute"] = time_after
    next_state["world"] = world
    return next_state


def _path_parts(path: Any) -> list[str]:
    if isinstance(path, str):
        parts = path.split(".") if path else []
    elif isinstance(path, (list, tuple)):
        parts = [str(p) for p in path]
    else:
        raise IntegrityError("patch path must be a dotted string or array")
    if not parts or any(not p or p in {"__proto__", ".."} for p in parts):
        raise IntegrityError("invalid patch path")
    if parts[0] not in _ALLOWED_BUSINESS_ROOTS:
        raise IntegrityError("patch path must target a business state root")
    return parts


def _locate(root: dict[str, Any], parts: list[str], *, create: bool = False) -> tuple[Any, str]:
    parent: Any = root
    for part in parts[:-1]:
        if not isinstance(parent, dict):
            raise IntegrityError("patch path traverses a non-object")
        if part not in parent:
            if not create:
                raise IntegrityError("patch path does not exist")
            parent[part] = {}
        parent = parent[part]
    return parent, parts[-1]


def apply_patch(state: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one of the contract's five JSON patch operations."""

    if not isinstance(patch, Mapping):
        raise IntegrityError("patch must be an object")
    op = patch.get("op")
    parts = _path_parts(patch.get("path"))
    result = copy.deepcopy(dict(state))
    if op == "set":
        parent, key = _locate(result, parts, create=True)
        if not isinstance(parent, dict):
            raise IntegrityError("set target is not an object")
        parent[key] = copy.deepcopy(patch.get("value"))
    elif op == "add":
        parent, key = _locate(result, parts, create=True)
        old = parent.get(key, 0) if isinstance(parent, dict) else None
        if not isinstance(old, (int, float)) or isinstance(old, bool) or not isinstance(patch.get("value"), (int, float)) or isinstance(patch.get("value"), bool):
            raise IntegrityError("add requires numeric values")
        parent[key] = old + patch["value"]
    elif op == "append_unique":
        parent, key = _locate(result, parts, create=True)
        if not isinstance(parent, dict):
            raise IntegrityError("append_unique target is not an object")
        values = parent.setdefault(key, [])
        if not isinstance(values, list):
            raise IntegrityError("append_unique target must be an array")
        value = copy.deepcopy(patch.get("value"))
        if value not in values:
            values.append(value)
    elif op == "remove":
        parent, key = _locate(result, parts)
        if isinstance(parent, dict):
            if key not in parent:
                raise IntegrityError("remove target does not exist")
            if "value" in patch and isinstance(parent[key], list):
                try:
                    parent[key].remove(patch["value"])
                except ValueError as exc:
                    raise IntegrityError("remove value does not exist") from exc
            else:
                del parent[key]
        else:
            raise IntegrityError("remove target is not an object")
    elif op == "merge":
        parent, key = _locate(result, parts, create=True)
        value = patch.get("value")
        if not isinstance(value, Mapping):
            raise IntegrityError("merge requires an object value")
        current = parent.get(key, {})
        if not isinstance(current, dict):
            raise IntegrityError("merge target must be an object")
        current.update(copy.deepcopy(dict(value)))
        parent[key] = current
    else:
        raise IntegrityError(f"unknown patch operation: {op}")
    return result


class CampaignStore:
    def __init__(self, campaign_dir: Path, connection: sqlite3.Connection):
        self.campaign_dir = campaign_dir
        self.db_path = campaign_dir / "campaign.sqlite3"
        self.exports_dir = campaign_dir / "exports"
        self._db = connection
        self._read_only = False

    @staticmethod
    def _safe_dir(root: Path, campaign_id: str) -> Path:
        if not isinstance(campaign_id, str) or not CAMPAIGN_RE.fullmatch(campaign_id):
            raise CampaignStoreError("campaign_id contains unsafe characters")
        root = root.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = root / campaign_id
        if path.resolve().parent != root:
            raise CampaignStoreError("campaign path escapes saves root")
        return path

    @classmethod
    def create(cls, saves_root: str | os.PathLike[str], campaign_id: str, compiled_world: Mapping[str, Any], initial_state: Mapping[str, Any]) -> "CampaignStore":
        root = Path(saves_root)
        campaign_dir = cls._safe_dir(root, campaign_id)
        if campaign_dir.exists() or campaign_dir.is_symlink():
            raise FileExistsError(f"campaign already exists: {campaign_id}")
        campaign_dir.mkdir()
        try:
            (campaign_dir / "exports").mkdir()
            db = sqlite3.connect(campaign_dir / "campaign.sqlite3")
            store = cls(campaign_dir, db)
            store._configure()
            world = _plain(compiled_world)
            if not isinstance(world, Mapping):
                raise IntegrityError("compiled_world must be an object")
            if not isinstance(initial_state, Mapping):
                raise IntegrityError("initial_state must be an object")
            state = copy.deepcopy(dict(initial_state))
            if "turn" in state:
                raise IntegrityError("root state.turn is unsupported; use state.campaign.turn")
            campaign = state.get("campaign")
            if not isinstance(campaign, dict):
                raise IntegrityError("initial state campaign must be an object")
            campaign.setdefault("turn", 0)
            campaign.setdefault("time_minute", 0)
            campaign.setdefault("current_tier", 0)
            state["campaign"] = campaign
            _validate_business_state(state, campaign_id)
            state["world"].setdefault("minute", campaign["time_minute"])
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "campaign_id": campaign_id,
                "blueprint_hash": sha256_json(world),
                "initial_state_hash": _state_hash(state),
                "status": "ACTIVE",
            }
            with db:
                store._create_schema()
                db.execute("INSERT INTO manifest(key,value) VALUES (?,?)", ("manifest", _json(manifest)))
                db.execute("INSERT INTO manifest(key,value) VALUES (?,?)", ("compiled_world", _json(world)))
                db.execute("INSERT INTO manifest(key,value) VALUES (?,?)", ("initial_state", _json(state)))
                db.execute("INSERT INTO snapshot(id,turn,state_hash,state_json) VALUES (1,?,?,?)", (0, _state_hash(state), _json(state)))
            return store
        except Exception:
            try:
                if 'db' in locals():
                    db.close()
            finally:
                # Creation is all-or-nothing; this directory is ours because
                # existence was checked above.
                import shutil
                shutil.rmtree(campaign_dir, ignore_errors=True)
            raise

    @classmethod
    def open(cls, saves_root: str | os.PathLike[str], campaign_id: str) -> "CampaignStore":
        root = Path(saves_root).expanduser().resolve()
        campaign_dir = cls._safe_dir(root, campaign_id)
        if not campaign_dir.exists() or campaign_dir.is_symlink() or not campaign_dir.is_dir():
            raise FileNotFoundError(campaign_id)
        db_path = campaign_dir / "campaign.sqlite3"
        if db_path.is_symlink() or not db_path.is_file():
            raise IntegrityError("campaign database is not a regular file")
        db = sqlite3.connect(db_path)
        store = cls(campaign_dir, db)
        store._configure()
        try:
            store._validate_manifest()
            store.verify()
        except Exception as exc:
            # A committed narration is authoritative; a failed derived draft
            # write is recoverable from that DB record after reopening.
            if isinstance(exc, IntegrityError) and any(token in str(exc) for token in ("novel draft missing", "novel draft is stale")):
                store._read_only = False
                return store
            store._read_only = True
            db.close()
            raise
        return store

    @classmethod
    def list_campaigns(cls, saves_root: str | os.PathLike[str]) -> list[dict[str, Any]]:
        root = Path(saves_root).expanduser().resolve()
        if not root.exists():
            return []
        result: list[dict[str, Any]] = []
        for path in sorted(root.iterdir()):
            if not path.is_dir() or path.is_symlink() or not CAMPAIGN_RE.fullmatch(path.name):
                continue
            try:
                store = cls.open(root, path.name)
            except Exception:
                continue
            try:
                result.append(store.manifest())
            finally:
                store.close()
        return result

    def _configure(self) -> None:
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA synchronous=FULL")

    def _ensure_exports_dir(self) -> None:
        if self.exports_dir.exists() or self.exports_dir.is_symlink():
            if self.exports_dir.is_symlink() or not self.exports_dir.is_dir() or self.exports_dir.resolve().parent != self.campaign_dir.resolve():
                raise IntegrityError("exports path is not a safe campaign child")
        else:
            self.exports_dir.mkdir()

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE manifest (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE snapshot (id INTEGER PRIMARY KEY CHECK(id=1), turn INTEGER NOT NULL, state_hash TEXT NOT NULL, state_json TEXT NOT NULL);
            CREATE TABLE events (seq INTEGER PRIMARY KEY, turn INTEGER NOT NULL, event_id TEXT UNIQUE NOT NULL, event_type TEXT NOT NULL, actor_id TEXT NOT NULL, patches_json TEXT NOT NULL, facts_json TEXT NOT NULL, details_json TEXT NOT NULL, prev_hash TEXT NOT NULL, state_before_hash TEXT NOT NULL, state_after_hash TEXT NOT NULL, event_hash TEXT NOT NULL);
            CREATE TABLE commands (request_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, response_json TEXT NOT NULL);
            CREATE TABLE narration_requests (request_id TEXT PRIMARY KEY, turn INTEGER NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE narratives (request_id TEXT PRIMARY KEY, turn INTEGER NOT NULL, response_json TEXT NOT NULL, response_hash TEXT NOT NULL);
            CREATE TABLE exports (name TEXT PRIMARY KEY, content_hash TEXT NOT NULL, updated_at TEXT NOT NULL);
            """
        )

    def _validate_manifest(self) -> None:
        if not self.exports_dir.is_dir() or self.exports_dir.is_symlink() or self.exports_dir.resolve().parent != self.campaign_dir.resolve():
            raise IntegrityError("exports directory is missing or unsafe")
        row = self._db.execute("SELECT value FROM manifest WHERE key='manifest'").fetchone()
        world = self._db.execute("SELECT value FROM manifest WHERE key='compiled_world'").fetchone()
        if not row or not world:
            raise IntegrityError("manifest is incomplete")
        manifest = _loads(row[0])
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("campaign_id") != self.campaign_dir.name:
            raise IntegrityError("manifest identity mismatch")
        if manifest.get("blueprint_hash") != sha256_json(_loads(world[0])):
            raise IntegrityError("compiled blueprint hash mismatch")

    def _ensure_writable(self) -> None:
        if self._read_only:
            raise ReadOnlyCampaignError("campaign is read-only after integrity failure")

    def _canonical_player_observation(self, state: Mapping[str, Any], events: Iterable[Any]) -> Any:
        """Return the engine projection when the compiled world supports it.

        Tiny storage-only fixtures may intentionally use a non-engine blueprint;
        those are still checked for object-ness, while real compiled worlds are
        compared byte-for-byte with ``project_player_view``.
        """
        world = self.get_compiled_world()
        if "actions" not in world:
            return None
        try:
            from tgn.projection import project_player_view
            return _plain(project_player_view(world, state, events))
        except Exception as exc:
            raise IntegrityError(f"cannot compute canonical player projection: {exc}") from exc

    def _check_player_observation(self, state: Mapping[str, Any], events: Iterable[Any], supplied: Any) -> None:
        if not isinstance(supplied, Mapping):
            raise IntegrityError("player_observation must be an object")
        canonical = self._canonical_player_observation(state, events)
        if canonical is not None and _plain(supplied) != canonical:
            raise IntegrityError("player_observation does not match canonical player projection")

    def manifest(self) -> dict[str, Any]:
        row = self._db.execute("SELECT value FROM manifest WHERE key='manifest'").fetchone()
        return _loads(row[0]) if row else {}

    def get_compiled_world(self) -> dict[str, Any]:
        row = self._db.execute("SELECT value FROM manifest WHERE key='compiled_world'").fetchone()
        if not row:
            raise IntegrityError("compiled world missing")
        return _loads(row[0])

    def get_state(self) -> dict[str, Any]:
        row = self._db.execute("SELECT state_json FROM snapshot WHERE id=1").fetchone()
        if not row:
            raise IntegrityError("snapshot missing")
        return _loads(row[0])

    def get_events(self) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT * FROM events ORDER BY seq").fetchall()
        return [self._event_from_row(row) for row in rows]

    def _event_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "seq": row["seq"], "turn": row["turn"], "event_id": row["event_id"],
            "event_type": row["event_type"], "actor_id": row["actor_id"],
            "patches": _loads(row["patches_json"]), "facts": _loads(row["facts_json"]),
            "details": _loads(row["details_json"]), "prev_hash": row["prev_hash"],
            "state_before_hash": row["state_before_hash"], "state_after_hash": row["state_after_hash"],
            "event_hash": row["event_hash"],
        }

    def pending_narration(self) -> dict[str, Any] | None:
        row = self._db.execute("SELECT payload_json FROM narration_requests WHERE status='PENDING' ORDER BY turn LIMIT 1").fetchone()
        return _loads(row[0]) if row else None

    def get_command_response(self, request_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT response_json FROM commands WHERE request_id=?", (request_id,)).fetchone()
        return _loads(row[0]) if row else None

    def begin_opening(
        self,
        request_id: str,
        facts: Iterable[Mapping[str, Any]],
        player_observation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Commit the turn-zero world entry before any prose is generated.

        The opening is a real, hash-chained event with no state mutation.  This
        gives the narrator a grounded prologue while preserving turn zero for
        the player's first decision.
        """

        self._ensure_writable()
        fact_values = []
        for fact in facts:
            if not isinstance(fact, Mapping):
                raise IntegrityError("fact must be an object")
            fact_values.append(dict(fact))
        if player_observation is None:
            observation = {}
        elif isinstance(player_observation, Mapping):
            observation = dict(player_observation)
        else:
            raise IntegrityError("player_observation must be an object")
        command_payload = {"facts": fact_values, "player_observation": observation}
        payload_hash = sha256_json(command_payload)
        existing = self._db.execute(
            "SELECT payload_hash,response_json FROM commands WHERE request_id=?",
            (request_id,),
        ).fetchone()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise CommandConflict("request_id was reused with a different opening")
            return _loads(existing["response_json"])
        if self.manifest().get("status") != "ACTIVE":
            raise CampaignStoreError("opening requires an active campaign")
        if self.pending_narration() is not None:
            raise CampaignStoreError("pending narration must be committed before opening")
        if self._db.execute("SELECT 1 FROM events LIMIT 1").fetchone():
            raise CampaignStoreError("opening can only be committed before the first event")
        turn, state_hash, state = self._current()
        if turn != 0:
            raise CampaignStoreError("opening requires turn zero")
        campaign = _campaign_meta(state)
        committed_facts: list[dict[str, Any]] = []
        for index, raw_fact in enumerate(fact_values):
            _validate_fact(raw_fact, assigned=True)
            committed_facts.append({**raw_fact, "fact_id": f"f-00000001-{index:02d}"})
        details = {
            "turn_after": 0,
            "time_after": int(campaign.get("time_minute", 0)),
            "tier_after": campaign.get("current_tier", 0),
            "opening": True,
        }
        event = {
            "seq": 1,
            "turn": 0,
            "event_id": "e-00000001",
            "event_type": "campaign.started",
            "actor_id": "world",
            "patches": [],
            "facts": committed_facts,
            "details": details,
            "prev_hash": "genesis",
            "state_before_hash": state_hash,
            "state_after_hash": state_hash,
        }
        event["event_hash"] = sha256_json(event)
        projection_event = {**event, "facts": [{k: v for k, v in fact.items() if k != "fact_id"} for fact in committed_facts]}
        self._check_player_observation(state, [projection_event], observation)
        request = build_narration_request(
            self.campaign_dir.name,
            0,
            [event],
            observation,
            {"opening": True, "locale": self._world_locale()},
        )
        request_dict = _plain(request.to_dict())
        response = {
            "request_id": request_id,
            "turn": 0,
            "state_hash": state_hash,
            "event_ids": [event["event_id"]],
            "narration_request": request_dict,
        }
        with self._db:
            self._db.execute(
                "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event["seq"], event["turn"], event["event_id"], event["event_type"],
                    event["actor_id"], _json(event["patches"]), _json(event["facts"]),
                    _json(event["details"]), event["prev_hash"], event["state_before_hash"],
                    event["state_after_hash"], event["event_hash"],
                ),
            )
            self._db.execute("INSERT INTO commands VALUES (?,?,?)", (request_id, payload_hash, _json(response)))
            self._db.execute(
                "INSERT INTO narration_requests VALUES (?,?,?,'PENDING')",
                (request.request_id, request.turn, _json(request_dict)),
            )
        return response

    def _current(self) -> tuple[int, str, dict[str, Any]]:
        row = self._db.execute("SELECT turn,state_hash,state_json FROM snapshot WHERE id=1").fetchone()
        if not row:
            raise IntegrityError("snapshot missing")
        state = _loads(row["state_json"])
        campaign = _campaign_meta(state)
        if int(row["turn"]) != int(campaign.get("turn", -1)):
            raise IntegrityError("snapshot turn disagrees with state.campaign.turn")
        return int(campaign["turn"]), row["state_hash"], state

    def commit_resolution(self, request_id: str, resolution: EngineResolution) -> dict[str, Any]:
        self._ensure_writable()
        payload = _plain(resolution)
        payload_hash = sha256_json(payload)
        existing = self._db.execute("SELECT payload_hash,response_json FROM commands WHERE request_id=?", (request_id,)).fetchone()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise CommandConflict("request_id was reused with a different payload")
            return _loads(existing["response_json"])
        if self.manifest().get("status") != "ACTIVE":
            raise CampaignStoreError("new resolutions require an active campaign")
        if self.pending_narration() is not None:
            raise CampaignStoreError("pending narration must be committed before the next turn")
        current_turn, current_hash, current_state = self._current()
        _validate_business_state(current_state, self.campaign_dir.name)
        if resolution.expected_turn != current_turn or resolution.expected_state_hash != current_hash:
            raise CampaignStoreError("stale resolution")
        if not resolution.events:
            raise IntegrityError("resolution must contain at least one event")
        state = current_state
        seq_row = self._db.execute("SELECT COALESCE(MAX(seq),0) AS seq FROM events").fetchone()
        seq = int(seq_row["seq"])
        previous_hash = self._db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = previous_hash[0] if previous_hash else "genesis"
        events: list[dict[str, Any]] = []
        for draft in resolution.events:
            if not isinstance(draft, EventDraft):
                draft = EventDraft(**dict(draft))
            if not isinstance(draft.event_type, str) or not draft.event_type.strip():
                raise IntegrityError("event_type must be a non-empty string")
            if not isinstance(draft.actor_id, str) or not draft.actor_id.strip():
                raise IntegrityError("actor_id must be a non-empty string")
            if not isinstance(draft.details, Mapping):
                raise IntegrityError("event details must be an object")
            seq += 1
            before_hash = _state_hash(state)
            details = _plain(draft.details)
            next_state = _apply_event_state(state, draft.patches, details)
            turn = int(next_state["campaign"]["turn"])
            event_id = f"e-{seq:08d}"
            facts = []
            for index, raw_fact in enumerate(draft.facts):
                if not isinstance(raw_fact, Mapping):
                    raise IntegrityError("fact must be an object")
                fact = dict(raw_fact)
                _validate_fact(fact, assigned=True)
                fact["fact_id"] = f"f-{seq:08d}-{index:02d}"
                facts.append(fact)
            after_hash = _state_hash(next_state)
            event = {
                "seq": seq, "turn": turn, "event_id": event_id, "event_type": draft.event_type,
                "actor_id": draft.actor_id, "patches": _plain(draft.patches), "facts": facts,
                "details": details, "prev_hash": prev_hash,
                "state_before_hash": before_hash, "state_after_hash": after_hash,
            }
            event["event_hash"] = sha256_json(event)
            events.append(event)
            state, prev_hash = next_state, event["event_hash"]
        # The engine's state is authoritative only after independent replay.
        expected_new_state = copy.deepcopy(_plain(resolution.new_state))
        if state != expected_new_state:
            raise IntegrityError("resolution new_state does not match replayed patches")
        _validate_business_state(state, self.campaign_dir.name)
        new_hash = _state_hash(state)
        final_turn = int(state["campaign"]["turn"])
        # The engine projection is computed from draft facts before storage
        # assigns durable fact_ids; use that same input for deterministic CAS.
        self._check_player_observation(state, resolution.events, resolution.player_observation)
        request = build_narration_request(self.campaign_dir.name, final_turn, events, resolution.player_observation, {"action_id": resolution.action_id, "locale": self._world_locale()})
        request_dict = _plain(request.to_dict())
        response = {"request_id": request_id, "action_id": resolution.action_id, "turn": final_turn, "state_hash": new_hash, "event_ids": [event["event_id"] for event in events], "narration_request": request_dict}
        try:
            with self._db:
                for event in events:
                    self._db.execute(
                        "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (event["seq"], event["turn"], event["event_id"], event["event_type"], event["actor_id"], _json(event["patches"]), _json(event["facts"]), _json(event["details"]), event["prev_hash"], event["state_before_hash"], event["state_after_hash"], event["event_hash"]),
                    )
                self._db.execute("UPDATE snapshot SET turn=?,state_hash=?,state_json=? WHERE id=1", (final_turn, new_hash, _json(state)))
                self._db.execute("INSERT INTO commands VALUES (?,?,?)", (request_id, payload_hash, _json(response)))
                self._db.execute("INSERT INTO narration_requests VALUES (?,?,?,'PENDING')", (request.request_id, request.turn, _json(request_dict)))
            return response
        except Exception:
            raise

    def commit_narration(self, response: Any) -> dict[str, Any]:
        self._ensure_writable()
        pending = self.pending_narration()
        if pending is None:
            # Idempotent replay of an already committed response.
            candidate = response.to_dict() if hasattr(response, "to_dict") else dict(response)
            row = self._db.execute("SELECT response_json FROM narratives WHERE request_id=?", (candidate.get("request_id"),)).fetchone()
            if row and _loads(row[0]) == candidate:
                # A successful DB commit can be followed by a disk fault.  The
                # same response is therefore also the recovery token.
                self._refresh_draft()
                if self.manifest().get("status") in {"STOPPING", "STOPPED"}:
                    if self.manifest().get("status") == "STOPPING":
                        self.export_final()
                    else:
                        self._write_final_exports()
                return candidate
            raise CampaignStoreError("no pending narration")
        candidate = response.to_dict() if hasattr(response, "to_dict") else dict(response)
        validated = validate_narration_response(pending, candidate)
        response_dict = _plain(validated.to_dict())
        response_hash = sha256_json(response_dict)
        row = self._db.execute("SELECT response_json FROM narratives WHERE request_id=?", (validated.request_id,)).fetchone()
        if row:
            if _loads(row[0]) != response_dict:
                raise CommandConflict("narration response conflict")
            return response_dict
        ending = bool(self._db.execute("SELECT 1 FROM events WHERE event_type='campaign.ending_requested' AND turn=?", (int(pending["turn"]),)).fetchone())
        with self._db:
            self._db.execute("INSERT INTO narratives VALUES (?,?,?,?)", (validated.request_id, int(pending["turn"]), _json(response_dict), response_hash))
            self._db.execute("UPDATE narration_requests SET status='COMMITTED' WHERE request_id=?", (validated.request_id,))
        # The database transaction is authoritative.  A filesystem export can
        # fail independently and remains retryable without rolling back facts.
        self._refresh_draft()
        if ending:
            self._write_final_exports()
            manifest = self.manifest()
            manifest["status"] = "STOPPED"
            with self._db:
                self._db.execute("UPDATE manifest SET value=? WHERE key='manifest'", (_json(manifest),))
        return response_dict

    def recover_exports(self) -> dict[str, Any]:
        """Rebuild derived draft/final files after an interrupted disk write."""
        self._ensure_writable()
        if self._db.execute("SELECT 1 FROM narratives LIMIT 1").fetchone():
            self._refresh_draft()
        if self.manifest().get("status") == "STOPPING":
            return self.export_final()
        if self.manifest().get("status") == "STOPPED":
            self._write_final_exports()
            return _loads((self.exports_dir / "manifest.json").read_text(encoding="utf-8"))
        return {"status": self.manifest().get("status"), "draft": bool(self._db.execute("SELECT 1 FROM narratives LIMIT 1").fetchone())}

    def export_final(self) -> dict[str, Any]:
        """Rebuild final artifacts from the immutable DB, idempotently."""

        if self.manifest().get("status") not in {"STOPPING", "STOPPED"}:
            raise CampaignStoreError("final export requires STOPPING or STOPPED campaign")
        self._write_final_exports()
        if self.manifest().get("status") == "STOPPING":
            manifest = self.manifest()
            manifest["status"] = "STOPPED"
            with self._db:
                self._db.execute("UPDATE manifest SET value=? WHERE key='manifest'", (_json(manifest),))
        return _loads((self.exports_dir / "manifest.json").read_text(encoding="utf-8"))

    def _narratives(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            """
            SELECT n.turn,n.response_json,r.payload_json
            FROM narratives AS n
            JOIN narration_requests AS r ON r.request_id=n.request_id
            ORDER BY n.rowid
            """
        ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            request = _loads(row["payload_json"])
            values.append({
                "turn": int(row["turn"]),
                "context": dict(request.get("context", {})),
                **_loads(row["response_json"]),
            })
        return values

    @staticmethod
    def _chapter_heading(narrative: Mapping[str, Any]) -> str:
        context = narrative.get("context", {})
        if isinstance(context, Mapping) and context.get("opening"):
            return "## 序章"
        if isinstance(context, Mapping) and context.get("ending"):
            return "## 尾声"
        return f"## 第 {int(narrative['turn'])} 章"

    def _refresh_draft(self) -> None:
        self._ensure_exports_dir()
        title = self._world_title()
        lines = [f"# {title}", ""]
        for narrative in self._narratives():
            lines += [self._chapter_heading(narrative), narrative["prose"], ""]
        content = "\n".join(lines)
        self._atomic_text(self.exports_dir / "novel_draft.md", content)
        with self._db:
            self._db.execute("INSERT OR REPLACE INTO exports VALUES (?,?,datetime('now'))", ("novel_draft.md", sha256_text(content)))

    @staticmethod
    def _atomic_text(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or (path.exists() and path.resolve().parent != path.parent.resolve()):
            raise IntegrityError(f"unsafe export artifact path: {path.name}")
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def _write_final_exports(self) -> None:
        self._ensure_exports_dir()
        events = self.get_events()
        narratives = self._narratives()
        novel_lines = [f"# {self._world_title()}", ""]
        for narrative in narratives:
            novel_lines += [self._chapter_heading(narrative), narrative["prose"], ""]
        novel = "\n".join(novel_lines)
        history = _json({"campaign_id": self.campaign_dir.name, "events": events, "narratives": narratives})
        event_head = events[-1]["event_hash"] if events else "genesis"
        manifest = self.manifest()
        export_manifest = {
            "campaign_id": self.campaign_dir.name,
            "source_event_range": [events[0]["seq"], events[-1]["seq"]] if events else [],
            "source_event_count": len(events), "blueprint_hash": manifest["blueprint_hash"],
            "event_head": event_head, "novel_hash": sha256_text(novel), "history_hash": sha256_text(history), "final_ready": True,
        }
        manifest_text = _json(export_manifest)
        self._atomic_text(self.exports_dir / "novel.md", novel)
        self._atomic_text(self.exports_dir / "history.json", history)
        self._atomic_text(self.exports_dir / "manifest.json", manifest_text)
        with self._db:
            for name, content_hash in (("novel.md", sha256_text(novel)), ("history.json", sha256_text(history)), ("manifest.json", sha256_text(manifest_text))):
                self._db.execute("INSERT OR REPLACE INTO exports VALUES (?,?,datetime('now'))", (name, content_hash))

    def _world_title(self) -> str:
        world = self.get_compiled_world()
        title = world.get("title") or (world.get("metadata", {}).get("title") if isinstance(world.get("metadata"), Mapping) else None)
        return str(title or "TheGreatNovel")

    def _world_locale(self) -> str:
        world = self.get_compiled_world()
        locale = world.get("locale") or (world.get("metadata", {}).get("locale") if isinstance(world.get("metadata"), Mapping) else None)
        return str(locale or "zh-CN")

    def begin_end(self, request_id: str, reason: str = "player_requested") -> dict[str, Any]:
        self._ensure_writable()
        existing = self.get_command_response(request_id)
        if existing is not None:
            row = self._db.execute("SELECT payload_hash FROM commands WHERE request_id=?", (request_id,)).fetchone()
            if row and row["payload_hash"] != sha256_json({"reason": reason}):
                raise CommandConflict("request_id was reused with a different ending reason")
            return existing
        manifest = self.manifest()
        if manifest.get("status") != "ACTIVE":
            raise CampaignStoreError("ending can only begin from an active campaign")
        pending = self.pending_narration()
        if pending is not None:
            raise CampaignStoreError("pending narration must be committed before ending")
        turn, state_hash, state = self._current()
        seq = int(self._db.execute("SELECT COALESCE(MAX(seq),0) AS seq FROM events").fetchone()["seq"]) + 1
        prev = self._db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev[0] if prev else "genesis"
        campaign = _campaign_meta(state)
        details = {"reason": str(reason), "turn_after": int(campaign["turn"]), "time_after": int(campaign.get("time_minute", 0)), "tier_after": campaign.get("current_tier", 0)}
        ending_fact = {"fact_id": f"f-{seq:08d}-00", "text": "玩家决定让当前卷暂歇。", "visibility": "public", "kind": "ending", "source": "player"}
        event = {"seq": seq, "turn": turn, "event_id": f"e-{seq:08d}", "event_type": "campaign.ending_requested", "actor_id": "player", "patches": [], "facts": [ending_fact], "details": details, "prev_hash": prev_hash, "state_before_hash": state_hash, "state_after_hash": state_hash}
        event["event_hash"] = sha256_json(event)
        request = build_narration_request(self.campaign_dir.name, turn, [event], {"ending": True}, {"reason": str(reason), "ending": True, "locale": self._world_locale()})
        request_dict = _plain(request.to_dict())
        payload = {"request_id": request_id, "turn": turn, "state_hash": state_hash, "event_ids": [event["event_id"]], "narration_request": request_dict}
        with self._db:
            self._db.execute("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (event["seq"], event["turn"], event["event_id"], event["event_type"], event["actor_id"], _json([]), _json(event["facts"]), _json(event["details"]), event["prev_hash"], event["state_before_hash"], event["state_after_hash"], event["event_hash"]))
            manifest["status"] = "STOPPING"
            self._db.execute("UPDATE manifest SET value=? WHERE key='manifest'", (_json(manifest),))
            self._db.execute("INSERT INTO commands VALUES (?,?,?)", (request_id, sha256_json({"reason": reason}), _json(payload)))
            self._db.execute("INSERT INTO narration_requests VALUES (?,?,?,'PENDING')", (request.request_id, request.turn, _json(request_dict)))
        return payload

    def verify(self) -> dict[str, Any]:
        try:
            quick = self._db.execute("PRAGMA quick_check").fetchone()[0]
            if quick != "ok":
                raise IntegrityError(f"sqlite quick_check: {quick}")
            self._validate_manifest()
            for name in ("novel.md", "history.json", "manifest.json", "novel_draft.md"):
                artifact = self.exports_dir / name
                if artifact.is_symlink() or (artifact.exists() and artifact.resolve().parent != self.exports_dir.resolve()):
                    raise IntegrityError(f"unsafe export artifact: {name}")
            initial_row = self._db.execute("SELECT value FROM manifest WHERE key='initial_state'").fetchone()
            if not initial_row:
                raise IntegrityError("initial state missing")
            state = _loads(initial_row[0])
            _validate_business_state(state, self.campaign_dir.name)
            if _state_hash(state) != self.manifest().get("initial_state_hash"):
                raise IntegrityError("initial state hash mismatch")
            status = self.manifest().get("status")
            if status not in STATUSES:
                raise IntegrityError("invalid campaign status")
            events = self.get_events()
            ending_events = [event for event in events if event["event_type"] == "campaign.ending_requested"]
            pending_rows = self._db.execute("SELECT request_id,status FROM narration_requests WHERE status='PENDING'").fetchall()
            if status == "ACTIVE" and ending_events:
                raise IntegrityError("active campaign contains an ending event")
            if status == "STOPPING" and len(ending_events) != 1:
                raise IntegrityError("stopping campaign must contain exactly one ending event")
            if status == "STOPPED":
                if len(ending_events) != 1 or pending_rows:
                    raise IntegrityError("stopped campaign has invalid ending/pending state")
            if status == "STOPPING" and len(pending_rows) > 1:
                raise IntegrityError("stopping campaign has multiple pending narrations")
            previous = "genesis"
            previous_state_hash = _state_hash(state)
            for event in events:
                if not isinstance(event["event_type"], str) or not event["event_type"].strip() or not isinstance(event["actor_id"], str) or not event["actor_id"].strip():
                    raise IntegrityError(f"event identity types invalid at {event.get('event_id')}")
                for fact in event.get("facts", ()):
                    _validate_fact(fact, assigned=False)
                if event["prev_hash"] != previous or event["state_before_hash"] != previous_state_hash:
                    raise IntegrityError(f"event chain mismatch at {event['event_id']}")
                replay = _apply_event_state(state, event["patches"], event["details"])
                if int(replay["campaign"]["turn"]) != int(event["turn"]):
                    raise IntegrityError(f"event metadata turn mismatch at {event['event_id']}")
                if _state_hash(replay) != event["state_after_hash"] or sha256_json({k: event[k] for k in event if k != "event_hash"}) != event["event_hash"]:
                    raise IntegrityError(f"event content mismatch at {event['event_id']}")
                state, previous_state_hash, previous = replay, event["state_after_hash"], event["event_hash"]
            snapshot = self._current()
            if snapshot[0] != _campaign_meta(state).get("turn") or snapshot[1] != _state_hash(state) or snapshot[2] != state:
                raise IntegrityError("snapshot does not match event replay")
            event_map = {event["event_id"]: event for event in events}
            for row in self._db.execute("SELECT request_id,payload_json,status FROM narration_requests").fetchall():
                if row["status"] not in {"PENDING", "COMMITTED"}:
                    raise IntegrityError("invalid narration request status")
                request = _loads(row["payload_json"])
                if request["request_hash"] != sha256_json({k: request[k] for k in request if k != "request_hash"}):
                    raise IntegrityError("narration request hash mismatch")
                if any(event_id not in event_map for event_id in request.get("event_ids", ())):
                    raise IntegrityError("narration references an unknown event")
                referenced = [event_map[event_id] for event_id in request.get("event_ids", ())]
                if referenced and int(request.get("turn", -1)) != max(int(event["turn"]) for event in referenced):
                    raise IntegrityError("narration turn does not match final replay turn")
                visible_facts = {
                    str(fact["fact_id"]): fact
                    for event_id in request.get("event_ids", ())
                    for fact in event_map[event_id].get("facts", ())
                    if fact.get("visibility", "public") in {"public", "player"} and fact.get("fact_id")
                }
                request_facts = {str(fact.get("fact_id")): fact for fact in request.get("required_claims", ())}
                if request_facts != visible_facts:
                    raise IntegrityError("narration claims do not match event facts")
                narrative = self._db.execute("SELECT response_json,response_hash FROM narratives WHERE request_id=?", (row["request_id"],)).fetchone()
                if row["status"] == "COMMITTED":
                    if not narrative:
                        raise IntegrityError("committed narration missing response")
                    narrative_value = _loads(narrative[0])
                    if narrative["response_hash"] != sha256_json(narrative_value):
                        raise IntegrityError("narrative response hash mismatch")
                    validate_narration_response(request, narrative_value)
                elif narrative:
                    raise IntegrityError("pending narration already has a committed response")
            committed_count = self._db.execute("SELECT COUNT(*) FROM narratives").fetchone()[0]
            if committed_count and not (self.exports_dir / "novel_draft.md").is_file():
                raise IntegrityError("novel draft missing for committed narration")
            if committed_count:
                draft_lines = [f"# {self._world_title()}", ""]
                for narrative in self._narratives():
                    draft_lines += [self._chapter_heading(narrative), narrative["prose"], ""]
                draft_hash = sha256_text("\n".join(draft_lines))
                draft_path = self.exports_dir / "novel_draft.md"
                if sha256_text(draft_path.read_text(encoding="utf-8")) != draft_hash:
                    raise IntegrityError("novel draft is stale")
            for export in self._db.execute("SELECT name,content_hash FROM exports").fetchall():
                artifact = self.exports_dir / export["name"]
                if not artifact.is_file() or sha256_text(artifact.read_text(encoding="utf-8")) != export["content_hash"]:
                    raise IntegrityError(f"export artifact hash mismatch: {export['name']}")
            final_manifest_path = self.exports_dir / "manifest.json"
            if status in {"STOPPING", "STOPPED"} and final_manifest_path.is_file():
                export_manifest = _loads(final_manifest_path.read_text(encoding="utf-8"))
                event_head = events[-1]["event_hash"] if events else "genesis"
                expected_range = [events[0]["seq"], events[-1]["seq"]] if events else []
                expected = {
                    "campaign_id": self.campaign_dir.name,
                    "source_event_range": expected_range,
                    "source_event_count": len(events),
                    "blueprint_hash": self.manifest()["blueprint_hash"],
                    "event_head": event_head,
                    "final_ready": True,
                }
                if any(export_manifest.get(key) != value for key, value in expected.items()):
                    raise IntegrityError("final export manifest is stale")
            if status == "STOPPED":
                if not final_manifest_path.is_file():
                    raise IntegrityError("stopped campaign has no export manifest")
                export_manifest = _loads(final_manifest_path.read_text(encoding="utf-8"))
                novel_path = self.exports_dir / "novel.md"
                history_path = self.exports_dir / "history.json"
                if not novel_path.is_file() or not history_path.is_file() or not export_manifest.get("final_ready"):
                    raise IntegrityError("stopped campaign has incomplete final exports")
                if export_manifest.get("novel_hash") != sha256_text(novel_path.read_text(encoding="utf-8")) or export_manifest.get("history_hash") != sha256_text(history_path.read_text(encoding="utf-8")):
                    raise IntegrityError("final export content hash mismatch")
            return {"ok": True, "event_count": len(self.get_events()), "state_hash": snapshot[1], "status": self.manifest().get("status")}
        except Exception as exc:
            self._read_only = True
            if isinstance(exc, IntegrityError):
                raise
            raise IntegrityError(str(exc)) from exc

    def close(self) -> None:
        self._db.close()
