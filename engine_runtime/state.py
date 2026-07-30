"""YAML 存档与事件账本的运行时适配层。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from .events import append_event, apply_event, parse_events, standard_event
from .persistence import SQLiteEventStore


YAML_FILES = {
    "world": "world.yaml",
    "player": "player.yaml",
    "base": "base.yaml",
    "inventory": "inventory.yaml",
    "npcs": "npcs.yaml",
    "factions": "factions.yaml",
    "relationships": "relationships.yaml",
    "event_queue": "event_queue.yaml",
    # 群体/公共系统的状态同样必须进入 SQLite 快照；否则 YAML 看似更新、
    # 重放却完全不知道这些状态，校验会出现假绿。
    "region_state": "region_state.yaml",
    "population_state": "population_state.yaml",
    "public_system_state": "public_system_state.yaml",
    "market_state": "market_state.yaml",
    "ranking_state": "ranking_state.yaml",
    "comparative_state": "comparative_state.yaml",
    "rival_state": "rival_state.yaml",
    "meta": "meta.yaml",
}

LIST_STATE_KEYS = {"npcs", "factions", "relationships", "event_queue"}


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return value if isinstance(value, dict) else {}


def _write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(yaml.safe_dump(dict(value), allow_unicode=True, sort_keys=False), encoding="utf-8")


@dataclass
class GameState:
    save_dir: Path
    data: Dict[str, Any]
    store: SQLiteEventStore = field(init=False, repr=False)
    pending_records: list = field(default_factory=list, init=False, repr=False)
    projection_migration: Dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for key in YAML_FILES:
            self.data.setdefault(key, [] if key in LIST_STATE_KEYS else {})
        meta = self.data.setdefault("meta", {})
        if not meta.get("rng_seed"):
            meta["rng_seed"] = str(meta.get("world_name") or self.data.get("world", {}).get("name") or self.save_dir.name)
        self.store = SQLiteEventStore(self.save_dir / "campaign.sqlite3")
        snapshot = self.store.latest_snapshot()
        if snapshot is not None:
            yaml_projection = deepcopy(self.data)
            self.data = snapshot
            # 旧存档的快照可能早于新增投影文件。保留 YAML 中已有的值，
            # 下一次标准保存会把它们迁移进 SQLite，而不是把数据覆盖为空。
            for key in YAML_FILES:
                if key not in self.data:
                    self.data[key] = deepcopy(yaml_projection.get(key, [] if key in LIST_STATE_KEYS else {}))
                    self.projection_migration[key] = deepcopy(self.data[key])
            if "player_talent" not in self.data:
                self.data["player_talent"] = deepcopy(yaml_projection.get("player_talent", {}))
                self.projection_migration["player_talent"] = deepcopy(self.data["player_talent"])
            return
        event_path = self.save_dir / "event_log.md"
        legacy_events = [item["record"] for item in parse_events(event_path.read_text(encoding="utf-8") if event_path.exists() else "")]
        self.store.initialize(self.data, legacy_events, source_mode="sqlite_bootstrap")

    @property
    def meta(self) -> Dict[str, Any]:
        return self.data.setdefault("meta", {})

    @property
    def player(self) -> Dict[str, Any]:
        return self.data.setdefault("player", {})

    @property
    def inventory(self) -> Dict[str, Any]:
        return self.data.setdefault("inventory", {})

    @property
    def current_turn(self) -> int:
        return int(self.meta.get("current_turn", 0))

    def event_history(self):
        return [{"turn": int(record.get("turn", 0)), "record": record} for record in self.store.events()]

    def apply_and_append(self, record: Mapping[str, Any], persist: bool = True) -> None:
        projected = apply_event(self.data, record)
        self.data = projected
        if persist:
            self.store.append_transaction(record, projected)
            append_event(self.save_dir / "event_log.md", record)
        else:
            self.pending_records.append(dict(record))

    def commit_pending(self) -> None:
        if not self.pending_records:
            return
        self.store.append_batch(self.pending_records, self.data)
        for record in self.pending_records:
            append_event(self.save_dir / "event_log.md", record)
        self.pending_records = []

    def clear_pending(self) -> None:
        self.pending_records = []

    def migrate_projection_schema(self) -> bool:
        """把旧 SQLite 快照缺失的投影字段以标准事件迁移进账本。"""
        if not self.projection_migration:
            return False
        turn = self.current_turn
        record = standard_event(
            event_id=f"evt_schema_migrate_{turn:04d}_aux_v1",
            event_type="PROJECTION_SCHEMA_MIGRATED",
            actor="system",
            target=None,
            data={"projection_state": deepcopy(self.projection_migration)},
            turn=turn,
            timestamp=f"Day {self.meta.get('game_day', 1)} {self.meta.get('time_of_day', '清晨')}",
        )
        self.apply_and_append(record, persist=True)
        self.projection_migration = {}
        self.save()
        return True

    def save(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
        for key in YAML_FILES:
            self.data.setdefault(key, [] if key in LIST_STATE_KEYS else {})
        self.store.save_snapshot(self.data)
        for key, filename in YAML_FILES.items():
            if key == "world":
                wrapper = {"world": self.data.get("world", {}), "player_talent": self.data.get("player_talent", {})}
            else:
                wrapper = {key: self.data.get(key, {})}
            _write_yaml(self.save_dir / filename, wrapper)


def load_game_state(save_dir: str | Path) -> GameState:
    path = Path(save_dir).resolve()
    data: Dict[str, Any] = {}
    for key, filename in YAML_FILES.items():
        loaded = _load_yaml(path / filename)
        data[key] = loaded.get(key, [] if key in LIST_STATE_KEYS else {})
    world_package = _load_yaml(path / "world.yaml")
    data["world"] = world_package.get("world", {})
    data["player_talent"] = world_package.get("player_talent", {})
    data["story_text"] = (path / "story.md").read_text(encoding="utf-8") if (path / "story.md").exists() else ""
    return GameState(path, data)
