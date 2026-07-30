"""SQLite 事件存储、快照和投影校验。

Markdown/YAML 仍作为人类可读导出视图，但 SQLite 的 events 表和 snapshots
是运行时的事实源。每次行动在同一事务中写入事件与新快照。
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    world_name TEXT NOT NULL,
    base_turn INTEGER NOT NULL,
    base_state_json TEXT NOT NULL,
    source_mode TEXT NOT NULL DEFAULT 'sqlite',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor TEXT,
    target TEXT,
    timestamp TEXT,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE INDEX IF NOT EXISTS idx_events_campaign_turn ON events(campaign_id, turn);
CREATE TABLE IF NOT EXISTS snapshots (
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(campaign_id, turn),
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);
CREATE TABLE IF NOT EXISTS entities (
    campaign_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY(campaign_id, entity_type, entity_id)
);
CREATE TABLE IF NOT EXISTS relationships (
    campaign_id TEXT NOT NULL,
    relationship_id TEXT NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY(campaign_id, relationship_id)
);
CREATE TABLE IF NOT EXISTS scheduled_events (
    campaign_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    status TEXT NOT NULL,
    trigger_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY(campaign_id, event_id)
);
CREATE TABLE IF NOT EXISTS generation_runs (
    campaign_id TEXT PRIMARY KEY,
    compiler_version TEXT,
    profile TEXT,
    bundle_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _difference_paths(left: Any, right: Any, path: str = "") -> List[str]:
    if type(left) is not type(right):
        return [path or "$"]
    if isinstance(left, Mapping):
        paths = []
        for key in sorted(set(left) | set(right), key=str):
            child = f"{path}.{key}" if path else str(key)
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(_difference_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list):
        paths = []
        if len(left) != len(right):
            paths.append(path + ".length")
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            paths.extend(_difference_paths(left_item, right_item, f"{path}[{index}]"))
        return paths
    return [] if left == right else [path or "$"]


class SQLiteEventStore:
    def __init__(self, path: str | Path, campaign_id: Optional[str] = None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.campaign_id = campaign_id or self.path.parent.name
        self._ensure_schema()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def initialize(self, state: Mapping[str, Any], events: Iterable[Mapping[str, Any]] = (), source_mode: str = "sqlite") -> None:
        meta = state.get("meta", {}) if isinstance(state.get("meta", {}), Mapping) else {}
        world = state.get("world", {}) if isinstance(state.get("world", {}), Mapping) else {}
        current_turn = int(meta.get("current_turn", 0))
        base_state = deepcopy(dict(state))
        with self.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO campaigns(campaign_id, world_name, base_turn, base_state_json, source_mode, created_at) VALUES(?,?,?,?,?,?)",
                (self.campaign_id, str(world.get("name", meta.get("world_name", self.campaign_id))), current_turn, json.dumps(base_state, ensure_ascii=False), source_mode, _now()),
            )
            connection.execute(
                "INSERT OR REPLACE INTO snapshots(campaign_id, turn, state_json, created_at) VALUES(?,?,?,?)",
                (self.campaign_id, current_turn, json.dumps(dict(state), ensure_ascii=False), _now()),
            )
            self._upsert_projection(connection, state)
            for record in events:
                self._insert_event(connection, record)
            connection.commit()

    def _insert_event(self, connection: sqlite3.Connection, record: Mapping[str, Any]) -> None:
        connection.execute(
            "INSERT INTO events(event_id, campaign_id, turn, event_type, actor, target, timestamp, payload_json) VALUES(?,?,?,?,?,?,?,?)",
            (
                str(record.get("event_id")), self.campaign_id, int(record.get("turn", 0)), str(record.get("type", "")),
                str(record.get("actor", "")), None if record.get("target") is None else str(record.get("target")),
                str(record.get("timestamp", "")), json.dumps(dict(record), ensure_ascii=False),
            ),
        )

    def append_transaction(self, record: Mapping[str, Any], state: Mapping[str, Any]) -> None:
        """一次事务写入事件、快照、实体和关系投影。"""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._insert_event(connection, record)
            turn = int(record.get("turn", 0))
            connection.execute(
                "INSERT OR REPLACE INTO snapshots(campaign_id, turn, state_json, created_at) VALUES(?,?,?,?)",
                (self.campaign_id, turn, json.dumps(dict(state), ensure_ascii=False), _now()),
            )
            self._upsert_projection(connection, state)
            connection.commit()

    def append_batch(self, records: Iterable[Mapping[str, Any]], state: Mapping[str, Any]) -> None:
        """把一个 ActionPlan 的所有事件和最终投影作为一个 SQLite 事务提交。"""
        records = list(records)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            for record in records:
                self._insert_event(connection, record)
            turn = int(state.get("meta", {}).get("current_turn", 0)) if isinstance(state.get("meta", {}), Mapping) else 0
            connection.execute(
                "INSERT OR REPLACE INTO snapshots(campaign_id, turn, state_json, created_at) VALUES(?,?,?,?)",
                (self.campaign_id, turn, json.dumps(dict(state), ensure_ascii=False), _now()),
            )
            self._upsert_projection(connection, state)
            connection.commit()

    def save_snapshot(self, state: Mapping[str, Any]) -> None:
        meta = state.get("meta", {}) if isinstance(state.get("meta", {}), Mapping) else {}
        turn = int(meta.get("current_turn", 0))
        with self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO snapshots(campaign_id, turn, state_json, created_at) VALUES(?,?,?,?)",
                (self.campaign_id, turn, json.dumps(dict(state), ensure_ascii=False), _now()),
            )
            self._upsert_projection(connection, state)
            connection.commit()

    def _upsert_projection(self, connection: sqlite3.Connection, state: Mapping[str, Any]) -> None:
        for entity_type in ("npcs", "factions", "locations", "targets", "combat_targets", "enemy_definitions", "encounter_entities", "areas", "build_catalog"):
            if entity_type in {"npcs", "factions"}:
                raw = state.get(entity_type, {})
            else:
                raw = state.get("world", {}).get(entity_type, {}) if isinstance(state.get("world", {}), Mapping) else {}
            entries = raw.items() if isinstance(raw, Mapping) else ((item.get("id", item.get("name")), item) for item in raw if isinstance(item, Mapping)) if isinstance(raw, list) else ()
            for entity_id, entity in entries:
                if entity_id is None:
                    continue
                connection.execute(
                    "INSERT OR REPLACE INTO entities(campaign_id, entity_type, entity_id, state_json) VALUES(?,?,?,?)",
                    (self.campaign_id, entity_type, str(entity_id), json.dumps(entity, ensure_ascii=False)),
                )
        relationships = state.get("relationships", [])
        if isinstance(relationships, list):
            for relation in relationships:
                if not isinstance(relation, Mapping):
                    continue
                relation_id = relation.get("npc_id", relation.get("id"))
                if relation_id:
                    connection.execute(
                        "INSERT OR REPLACE INTO relationships(campaign_id, relationship_id, state_json) VALUES(?,?,?)",
                        (self.campaign_id, str(relation_id), json.dumps(dict(relation), ensure_ascii=False)),
                    )
        queue = state.get("event_queue", [])
        if isinstance(queue, list):
            for item in queue:
                if not isinstance(item, Mapping) or not item.get("id"):
                    continue
                connection.execute(
                    "INSERT OR REPLACE INTO scheduled_events(campaign_id, event_id, status, trigger_json, payload_json) VALUES(?,?,?,?,?)",
                    (self.campaign_id, str(item["id"]), str(item.get("status", "pending")), json.dumps(item.get("trigger_conditions", {}), ensure_ascii=False), json.dumps(dict(item), ensure_ascii=False)),
                )
        bundle = state.get("world", {}).get("generation_bundle") if isinstance(state.get("world", {}), Mapping) else None
        if isinstance(bundle, Mapping):
            connection.execute(
                "INSERT OR REPLACE INTO generation_runs(campaign_id, compiler_version, profile, bundle_json, created_at) VALUES(?,?,?,?,?)",
                (self.campaign_id, str(bundle.get("compiler_version", "")), str(bundle.get("profile", "")), json.dumps(dict(bundle), ensure_ascii=False), _now()),
            )

    def events(self) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT payload_json FROM events WHERE campaign_id=? ORDER BY turn, event_id", (self.campaign_id,)).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT state_json FROM snapshots WHERE campaign_id=? ORDER BY turn DESC LIMIT 1", (self.campaign_id,)).fetchone()
        return json.loads(row["state_json"]) if row else None

    def snapshot_before(self, turn: int) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM snapshots WHERE campaign_id=? AND turn < ? ORDER BY turn DESC LIMIT 1",
                (self.campaign_id, int(turn)),
            ).fetchone()
        return json.loads(row["state_json"]) if row else None

    def base_state(self) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute("SELECT base_state_json FROM campaigns WHERE campaign_id=?", (self.campaign_id,)).fetchone()
        return json.loads(row["base_state_json"]) if row else None

    def base_turn(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT base_turn FROM campaigns WHERE campaign_id=?", (self.campaign_id,)).fetchone()
        return int(row["base_turn"]) if row else 0

    def replay(self, apply_event) -> Optional[Dict[str, Any]]:
        base = self.base_state()
        if base is None:
            return None
        replayed = deepcopy(base)
        for record in self.events():
            # OPTIONS_PRESENTED 可在当前回合展示并持久化，不能因为它与
            # 初始化快照同回合就被重放器跳过。
            if int(record.get("turn", 0)) <= self.base_turn() and str(record.get("type", "")) != "OPTIONS_PRESENTED":
                continue
            replayed = apply_event(replayed, record)
        return replayed

    def verify_projection(self, apply_event) -> Dict[str, Any]:
        base = self.base_state()
        snapshot = self.latest_snapshot()
        if base is None or snapshot is None:
            return {"ok": False, "reason": "campaign or snapshot missing"}
        base_turn = self.base_turn()
        applied = sum(1 for record in self.events() if int(record.get("turn", 0)) > base_turn)
        replayed = self.replay(apply_event)
        equal = replayed == snapshot
        return {"ok": equal, "applied_events": applied, "base_turn": base_turn, "snapshot_turn": snapshot.get("meta", {}).get("current_turn"), "difference_paths": _difference_paths(replayed, snapshot)[:20] if not equal else [], "replayed": replayed if not equal else None}
