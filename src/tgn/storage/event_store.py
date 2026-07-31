"""SQLite event store with atomic commits."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class EventStoreError(Exception):
    """Raised when an event store operation fails."""
    pass


@dataclass
class CampaignRecord:
    """Campaign metadata stored in database."""
    campaign_id: str
    engine_version: str = "1.0.0"
    state_schema_version: int = 1
    seed: str = ""
    initial_state_json: str = ""
    initial_state_hash: str = ""
    created_at: str = ""


SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    engine_version TEXT NOT NULL DEFAULT '1.0.0',
    state_schema_version INTEGER NOT NULL DEFAULT 1,
    seed TEXT NOT NULL DEFAULT '',
    initial_state_json TEXT NOT NULL,
    initial_state_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    event_seq INTEGER NOT NULL,
    decision_seq INTEGER NOT NULL,
    game_minute INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT,
    action_id TEXT,
    causation_id TEXT,
    correlation_id TEXT,
    payload_json TEXT NOT NULL,
    state_hash_before TEXT NOT NULL,
    state_hash_after TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
    UNIQUE(campaign_id, event_seq)
);

CREATE INDEX IF NOT EXISTS idx_events_campaign_seq 
ON events(campaign_id, event_seq);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT NOT NULL,
    event_seq INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id),
    UNIQUE(campaign_id, event_seq)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_campaign_seq 
ON snapshots(campaign_id, event_seq);
"""


class EventStore:
    """SQLite-based event store with full transaction support."""
    
    def __init__(self, db_path: str | Path):
        """Initialize event store at given path."""
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._create_tables()
        return self._conn
    
    @contextmanager
    def transaction(self):
        """Context manager for atomic transactions."""
        cursor = self.connection.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE")
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise EventStoreError(f"Transaction failed: {e}")
        finally:
            cursor.close()
    
    def _create_tables(self) -> None:
        """Create schema tables."""
        cursor = self.connection.cursor()
        cursor.executescript(SCHEMA)
        self.connection.commit()
    
    def initialize(
        self,
        campaign_id: str,
        initial_state: dict[str, Any],
        seed: str = "",
        initial_state_hash: str = "",
    ) -> CampaignRecord:
        """Initialize a new campaign."""
        from ..core.hashing import canonical_json, state_hash
        
        if not initial_state_hash:
            initial_state_hash = state_hash(initial_state)
        
        initial_state_json = canonical_json(initial_state)
        now = __import__("datetime").datetime.now().isoformat()
        
        record = CampaignRecord(
            campaign_id=campaign_id,
            seed=seed,
            initial_state_json=initial_state_json,
            initial_state_hash=initial_state_hash,
            created_at=now,
        )
        
        with self.transaction() as cursor:
            cursor.execute(
                """INSERT INTO campaigns 
                   (campaign_id, engine_version, state_schema_version, seed, 
                    initial_state_json, initial_state_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.campaign_id,
                    record.engine_version,
                    record.state_schema_version,
                    record.seed,
                    record.initial_state_json,
                    record.initial_state_hash,
                    record.created_at,
                ),
            )
        
        return record
    
    def append_event(
        self,
        campaign_id: str,
        event_dict: dict[str, Any],
        state_hash_before: str,
        state_hash_after: str,
    ) -> None:
        """Append a single event and snapshot atomically."""
        with self.transaction() as cursor:
            # Insert event
            cursor.execute(
                """INSERT INTO events
                   (event_id, campaign_id, event_seq, decision_seq, game_minute,
                    event_type, actor_id, action_id, causation_id, correlation_id,
                    payload_json, state_hash_before, state_hash_after, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_dict["event_id"],
                    campaign_id,
                    event_dict["event_seq"],
                    event_dict["decision_seq"],
                    event_dict["game_minute"],
                    event_dict["event_type"],
                    event_dict.get("actor_id"),
                    event_dict.get("action_id"),
                    event_dict.get("causation_id"),
                    event_dict.get("correlation_id"),
                    json.dumps(event_dict["payload"], ensure_ascii=False),
                    state_hash_before,
                    state_hash_after,
                    event_dict.get("created_at", __import__("datetime").datetime.now().isoformat()),
                ),
            )
            
            # Insert snapshot
            from ..core.hashing import canonical_json
            
            cursor.execute(
                """INSERT OR REPLACE INTO snapshots
                   (campaign_id, event_seq, state_json, state_hash, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    campaign_id,
                    event_dict["event_seq"],
                    canonical_json(event_dict.get("_state_snapshot", {})),
                    state_hash_after,
                    __import__("datetime").datetime.now().isoformat(),
                ),
            )
    
    def latest_snapshot(self, campaign_id: str) -> dict[str, Any] | None:
        """Load the most recent snapshot for a campaign."""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT state_json FROM snapshots 
               WHERE campaign_id = ?
               ORDER BY event_seq DESC LIMIT 1""",
            (campaign_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row is None:
            return None
        
        return json.loads(row["state_json"])
    
    def all_events(self, campaign_id: str) -> list[dict[str, Any]]:
        """Load all events for a campaign in sequence order."""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT * FROM events 
               WHERE campaign_id = ?
               ORDER BY event_seq ASC""",
            (campaign_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        
        return [
            {
                "event_id": row["event_id"],
                "event_seq": row["event_seq"],
                "decision_seq": row["decision_seq"],
                "game_minute": row["game_minute"],
                "event_type": row["event_type"],
                "actor_id": row["actor_id"],
                "action_id": row["action_id"],
                "causation_id": row["causation_id"],
                "correlation_id": row["correlation_id"],
                "payload": json.loads(row["payload_json"]),
                "state_hash_before": row["state_hash_before"],
                "state_hash_after": row["state_hash_after"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    
    def get_campaign(self, campaign_id: str) -> CampaignRecord | None:
        """Load campaign metadata."""
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM campaigns WHERE campaign_id = ?",
            (campaign_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row is None:
            return None
        
        return CampaignRecord(
            campaign_id=row["campaign_id"],
            engine_version=row["engine_version"],
            state_schema_version=row["state_schema_version"],
            seed=row["seed"],
            initial_state_json=row["initial_state_json"],
            initial_state_hash=row["initial_state_hash"],
            created_at=row["created_at"],
        )
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
