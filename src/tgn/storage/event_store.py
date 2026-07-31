"""SQLite event store with atomic commits."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.hashing import canonical_json, state_hash
from ..core.models import DomainEvent, GameState


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


@dataclass
class SnapshotRecord:
    """Snapshot record returned by persistence layer."""
    campaign_id: str
    event_seq: int
    state: dict[str, Any]
    state_hash: str
    created_at: str


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
    ) -> CampaignRecord:
        """Initialize a new campaign. Hash computed internally."""
        initial_state_hash = state_hash(initial_state)
        initial_state_json = canonical_json(initial_state)
        now = datetime.now().isoformat()
        
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
    
    def append_transition(
        self,
        campaign_id: str,
        event: DomainEvent,
        state_before: GameState,
        state_after: GameState,
    ) -> None:
        """Append a transition atomically. Hashes computed internally."""
        # Compute hashes internally - caller cannot fake them
        hash_before = state_hash(state_before.__dict__)
        hash_after = state_hash(state_after.__dict__)
        snapshot_state = state_after.__dict__
        snapshot_json = canonical_json(snapshot_state)
        
        with self.transaction() as cursor:
            # Insert event
            cursor.execute(
                """INSERT INTO events
                   (event_id, campaign_id, event_seq, decision_seq, game_minute,
                    event_type, actor_id, action_id, causation_id, correlation_id,
                    payload_json, state_hash_before, state_hash_after, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.event_id,
                    campaign_id,
                    event.event_seq,
                    event.decision_seq,
                    event.game_minute,
                    event.event_type,
                    event.actor_id,
                    event.action_id,
                    event.causation_id,
                    event.correlation_id,
                    json.dumps(event.payload, ensure_ascii=False),
                    hash_before,
                    hash_after,
                    event.created_at,
                ),
            )
            
            # Insert snapshot using regular INSERT (not OR REPLACE)
            # This enforces immutability of facts
            cursor.execute(
                """INSERT INTO snapshots
                   (campaign_id, event_seq, state_json, state_hash, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    campaign_id,
                    event.event_seq,
                    snapshot_json,
                    hash_after,
                    datetime.now().isoformat(),
                ),
            )
    
    def latest_snapshot_record(self, campaign_id: str) -> SnapshotRecord | None:
        """Load the most recent snapshot as a typed record."""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT * FROM snapshots 
               WHERE campaign_id = ?
               ORDER BY event_seq DESC LIMIT 1""",
            (campaign_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        
        if row is None:
            return None
        
        return SnapshotRecord(
            campaign_id=row["campaign_id"],
            event_seq=row["event_seq"],
            state=json.loads(row["state_json"]),
            state_hash=row["state_hash"],
            created_at=row["created_at"],
        )
    
    def all_event_records(self, campaign_id: str) -> list[dict[str, Any]]:
        """Load all event records as dictionaries with full fields."""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT * FROM events 
               WHERE campaign_id = ?
               ORDER BY event_seq ASC""",
            (campaign_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        
        results = []
        for row in rows:
            try:
                results.append(
                    {
                        "event_id": row["event_id"],
                        "campaign_id": row["campaign_id"],
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
                )
            except json.JSONDecodeError as e:
                # Malformed JSON in persisted record - indicate corruption
                raise ValueError(f"Malformed JSON in event {row['event_seq']}: {e}") from e
        
        return results
    
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
