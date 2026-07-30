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

-- ============================================================================
-- 第十九轮对话新增：全民系统流专用表
-- ============================================================================

-- 区域信息
CREATE TABLE IF NOT EXISTS regions (
    region_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    name TEXT,
    population_count INTEGER DEFAULT 1000,
    current_phase TEXT,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);

-- 具体玩家代理（有名字的具体求生者）
CREATE TABLE IF NOT EXISTS peer_players (
    player_id TEXT,
    campaign_id TEXT NOT NULL,
    name TEXT,
    avatar_description TEXT,
    region_id TEXT,
    origin_background TEXT,
    profession_id TEXT DEFAULT NULL,
    PRIMARY KEY(player_id, campaign_id),
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);

-- 为职业关联创建索引以优化查询性能
CREATE INDEX IF NOT EXISTS idx_peer_profession ON peer_players(campaign_id, profession_id);

-- 玩家群体状态快照
CREATE TABLE IF NOT EXISTS player_population_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    region_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    total_players INTEGER NOT NULL,
    alive_count INTEGER NOT NULL,
    death_rate REAL,
    turn INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);

-- 排行榜数据
CREATE TABLE IF NOT EXISTS rankings (
    rank_id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    category TEXT NOT NULL,  -- overall, exploration, base, info, social
    rank_value REAL NOT NULL,
    percentile REAL,
    turn INTEGER NOT NULL,
    UNIQUE(campaign_id, player_id, category, turn)
);

CREATE INDEX IF NOT EXISTS idx_rankings_campaign_turn ON rankings(campaign_id, turn);

-- 排行榜快照（用于比较历史变化）
CREATE TABLE IF NOT EXISTS ranking_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    snapshot_data_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 成就目录和解锁记录
CREATE TABLE IF NOT EXISTS achievements (
    achievement_id TEXT PRIMARY KEY,
    catalog_id TEXT NOT NULL,
    name TEXT,
    description TEXT,
    difficulty_tier TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS achievement_unlocks (
    unlock_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    unlocked_at TEXT NOT NULL,
    is_first_of_region INTEGER DEFAULT 0,  -- 是否区域首杀/首建
    UNIQUE(campaign_id, player_id, achievement_id, turn)
);

-- 系统公告
CREATE TABLE IF NOT EXISTS system_announcements (
    announcement_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    announcement_type TEXT NOT NULL,  -- first_kill, first_build, rank_change, achievement
    content TEXT NOT NULL,
    scope TEXT NOT NULL,  -- global, regional, private
    related_player_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);

-- 频道消息（区域频道、私聊等）
CREATE TABLE IF NOT EXISTS regional_channels (
    channel_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    channel_type TEXT NOT NULL,  -- regional, trade, private, team
    channel_name TEXT,
    max_message_count INTEGER DEFAULT 100,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE TABLE IF NOT EXISTS channel_messages (
    message_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    sender_name TEXT,
    content_hash TEXT NOT NULL,  -- 内容哈希用于去重
    content_preview TEXT,
    turn INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_channel_messages_channel_turn ON channel_messages(channel_id, turn);

-- 私聊记录
CREATE TABLE IF NOT EXISTS private_messages (
    message_id TEXT PRIMARY KEY,
    sender_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    turn INTEGER NOT NULL,
    read_status INTEGER DEFAULT 0,
    sent_at TEXT NOT NULL,
    UNIQUE(sender_id, recipient_id, turn, content_hash)
);

-- 交易订单
CREATE TABLE IF NOT EXISTS trade_orders (
    order_id TEXT PRIMARY KEY,
    seller_id TEXT NOT NULL,
    buyer_id TEXT,  -- null 表示挂单待匹配
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price_per_unit REAL NOT NULL,
    currency_type TEXT DEFAULT 'resource',
    status TEXT NOT NULL,  -- active, fulfilled, cancelled, expired
    expiration_turn INTEGER,
    created_turn INTEGER NOT NULL,
    fulfilled_at TEXT,
    UNIQUE(item_id, seller_id, created_turn)  -- 同一回合一个卖家只能有一个未成交的同物品订单
);

-- 交易执行记录
CREATE TABLE IF NOT EXISTS trade_transactions (
    transaction_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    buyer_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    total_price REAL NOT NULL,
    turn INTEGER NOT NULL,
    executed_at TEXT NOT NULL,
    FOREIGN KEY(order_id) REFERENCES trade_orders(order_id)
);

-- 市场快照（价格趋势）
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    prices_json TEXT NOT NULL,
    supply_demand_index REAL,
    created_at TEXT NOT NULL
);

-- 玩家对比快照（主角相对优势）
CREATE TABLE IF NOT EXISTS comparative_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    protagonist_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    matched_peer_count INTEGER,
    peer_median_performance REAL,
    protagonist_performance REAL,
    percentile REAL,
    power_percentile REAL,
    resource_percentile REAL,
    base_percentile REAL,
    information_percentile REAL,
    comparative_result TEXT,
    main_causes_json TEXT,  -- JSON 数组的原因列表
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, protagonist_id, turn)
);

-- 竞争者关系
CREATE TABLE IF NOT EXISTS rivalries (
    rivalry_id TEXT PRIMARY KEY,
    protagonist_id TEXT NOT NULL,
    rival_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    rivalry_type TEXT NOT NULL,  -- competition, enmity, cooperation
    intensity_score REAL,
    turn_assessed INTEGER NOT NULL,
    assessment_notes TEXT,
    UNIQUE(protagonist_id, rival_id, campaign_id)
);

-- 玩家声望和标签
CREATE TABLE IF NOT EXISTS player_reputations (
    reputation_id TEXT PRIMARY KEY,
    player_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    regional_honor INTEGER DEFAULT 0,
    global_honor INTEGER DEFAULT 0,
    trading_credit REAL DEFAULT 0.0,
    leader_score REAL DEFAULT 0.0,
    tags_json TEXT,  -- JSON 数组的标签，如 "dangerous_person", "trader", "leader"
    created_at TEXT NOT NULL,
    UNIQUE(player_id, campaign_id, turn)
);

-- 队伍和公会
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    creator_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    formation_turn INTEGER NOT NULL,
    rules_text TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS team_memberships (
    membership_id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    join_turn INTEGER NOT NULL,
    leave_turn INTEGER,
    role TEXT,
    contribution_points REAL DEFAULT 0.0,
    UNIQUE(team_id, member_id)
);

CREATE TABLE IF NOT EXISTS guilds (
    guild_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    founder_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    formation_turn INTEGER NOT NULL,
    headquarters_location TEXT,
    minimum_level_requirement INTEGER DEFAULT 1,
    status TEXT DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS guild_memberships (
    membership_id TEXT PRIMARY KEY,
    guild_id TEXT NOT NULL,
    member_id TEXT NOT NULL,
    join_turn INTEGER NOT NULL,
    rank_or_title TEXT,
    contribution_points REAL DEFAULT 0.0,
    UNIQUE(guild_id, member_id)
);

-- 区域统计数据
CREATE TABLE IF NOT EXISTS regional_statistics (
    stat_id TEXT PRIMARY KEY,
    region_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    statistics_json TEXT NOT NULL,  -- 包含探索成功率、平均收益、死亡率等统计
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
            if int(record.get("turn", 0)) <= self.base_turn() and str(record.get("type", "")) not in {"OPTIONS_PRESENTED", "PROJECTION_SCHEMA_MIGRATED"}:
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


def insert_peer_agent(state, campaign_id: str, peer):
    """Write a peer agent to the entities table."""
    with state.store.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO entities (campaign_id, entity_type, entity_id, state_json) VALUES (?, ?, ?, ?)",
            (campaign_id, "peer_players", peer.id, json.dumps(peer.to_dict(), ensure_ascii=False)),
        )
        conn.commit()


def load_peer_agents(state, campaign_id: str):
    """Load all peer agents for a campaign from SQLite."""
    from engine_runtime.peer_agent import PeerAgent
    with state.store.connect() as conn:
        rows = conn.execute(
            "SELECT state_json FROM entities WHERE campaign_id = ? AND entity_type = 'peer_players'",
            (campaign_id,),
        ).fetchall()
    return [PeerAgent.from_dict(json.loads(row[0])) for row in rows]
