"""YAML 存档与事件账本的运行时适配层。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from .events import append_event, apply_event, parse_events


YAML_FILES = {
    "world": "world.yaml",
    "player": "player.yaml",
    "base": "base.yaml",
    "inventory": "inventory.yaml",
    "npcs": "npcs.yaml",
    "factions": "factions.yaml",
    "relationships": "relationships.yaml",
    "event_queue": "event_queue.yaml",
    "meta": "meta.yaml",
}


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
        path = self.save_dir / "event_log.md"
        return parse_events(path.read_text(encoding="utf-8") if path.exists() else "")

    def apply_and_append(self, record: Mapping[str, Any]) -> None:
        self.data = apply_event(self.data, record)
        append_event(self.save_dir / "event_log.md", record)

    def save(self) -> None:
        self.save_dir.mkdir(parents=True, exist_ok=True)
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
        data[key] = loaded.get(key, {} if key not in {"npcs", "factions", "relationships", "event_queue"} else [])
    world_package = _load_yaml(path / "world.yaml")
    data["world"] = world_package.get("world", {})
    data["player_talent"] = world_package.get("player_talent", {})
    data["story_text"] = (path / "story.md").read_text(encoding="utf-8") if (path / "story.md").exists() else ""
    return GameState(path, data)
