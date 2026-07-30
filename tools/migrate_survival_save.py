#!/usr/bin/env python3
"""
Migration tool for upgrading existing saves to new population engine schema.

This script:
1. Fixes deeply-nested YAML keys caused by triple-write bug
2. Clears fake ranking metrics from old system
3. Archives stale channel messages
4. Initializes peer_players in SQLite
5. Preserves all valid player progress (inventory, base, XP, etc.)

Usage:
    python tools/migrate_survival_save.py saves/灰烬列车
    python tools/migrate_survival_save.py saves/锈铁方舟
"""

import sys
import yaml
import json
import sqlite3
import random
import shutil
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers: unwrap deeply-nested YAML produced by triple-write bug
# ---------------------------------------------------------------------------

def unwrap_nested(data: dict, key: str) -> dict:
    """Recursively unwrap ``{key: {key: {key: {...}}}}`` into flat dict.

    Example:
        {"ranking_state": {"ranking_state": {"ranking_state": {"rankings_enabled": True}}}}
        -> {"rankings_enabled": True}
    """
    while isinstance(data, dict) and key in data and isinstance(data[key], dict) and key in data[key]:
        data = data[key]
    if isinstance(data, dict) and key in data:
        inner = data[key]
        if isinstance(inner, dict):
            return inner
    return data if isinstance(data, dict) else {}


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def step_backup(save_dir: Path) -> Path:
    """Create backup directory with copies of critical files."""
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = save_dir / f"backup_before_migration_{suffix}"
    backup_path.mkdir(exist_ok=True)

    critical_files = [
        "world.yaml", "meta.yaml", "ranking_state.yaml",
        "population_state.yaml", "public_system_state.yaml",
        "rival_state.yaml", "player.yaml", "inventory.yaml",
    ]
    copied = 0
    for fname in critical_files:
        src = save_dir / fname
        if src.exists():
            shutil.copy2(src, backup_path / fname)
            copied += 1

    print(f"  Backup created: {backup_path.name} ({copied} files copied)")
    return backup_path


def step_fix_ranking(save_dir: Path):
    """Clear fake ranking data and fix nesting."""
    ranking_file = save_dir / "ranking_state.yaml"
    if not ranking_file.exists():
        print("  [skip] ranking_state.yaml not found")
        return

    raw = load_yaml(ranking_file)

    # Unwrap potential nesting: ranking_state > ranking_state > ...
    rs = unwrap_nested(raw, "ranking_state")

    # Reset player ranking to unknown
    rs["player_rank_regional"] = None
    rs["player_rank_global"] = None
    rs.setdefault("player_percentile_regional", None)
    rs["player_percentile_regional"] = None

    # Clear leaderboards
    rs["leaderboards"] = []

    # Clear performance history if present
    if "performance_metrics_history" in rs:
        rs["performance_metrics_history"] = []

    # Keep season info intact
    rs.setdefault("rankings_enabled", True)

    save_yaml(ranking_file, {"ranking_state": rs})
    print("  Ranking state: cleared player_rank, leaderboards, percentiles")


def step_archive_channel(save_dir: Path):
    """Archive all existing channel messages."""
    public_file = save_dir / "public_system_state.yaml"
    if not public_file.exists():
        print("  [skip] public_system_state.yaml not found")
        return

    raw = load_yaml(public_file)
    ps = unwrap_nested(raw, "public_system_state")

    channel_feed = ps.get("channel_feed", [])
    archived_count = 0
    for msg in channel_feed:
        if not msg.get("archived", False):
            msg["archived"] = True
            msg["archive_reason"] = "pre_migration_legacy_data"
            archived_count += 1

    ps["channel_feed"] = channel_feed
    save_yaml(public_file, {"public_system_state": ps})
    print(f"  Channel feed: {archived_count} messages archived (total {len(channel_feed)})")


def step_fix_rival(save_dir: Path):
    """Fix nested rival_state and reset encounter data."""
    rival_file = save_dir / "rival_state.yaml"
    if not rival_file.exists():
        print("  [skip] rival_state.yaml not found")
        return

    raw = load_yaml(rival_file)
    rs = unwrap_nested(raw, "rival_state")

    # Reset encounter
    rs["last_rival_encounter"] = None
    rs["rival_competitions_active"] = []
    rs["rival_score_current"] = 0
    rs["rival_score_target"] = 0
    rs["rivalry_win_rate"] = 0.0

    # Preserve active_rivals list and relationships (they are valid)
    save_yaml(rival_file, {"rival_state": rs})
    print("  Rival state: cleared encounters, preserved active_rivals list")


def step_init_peers(save_dir: Path):
    """Initialize peer_players in SQLite from world.yaml initial_peers."""
    db_path = save_dir / "campaign.sqlite3"
    if not db_path.exists():
        print("  [skip] campaign.sqlite3 not found")
        return

    world_file = save_dir / "world.yaml"
    if not world_file.exists():
        print("  [skip] world.yaml not found")
        return

    world_data = load_yaml(world_file)
    # Try multiple possible paths for initial_peers
    peers = (
        world_data.get("world", {}).get("public_survival", {}).get("initial_peers", [])
        or world_data.get("initial_peers", [])
        or world_data.get("world", {}).get("genre_contract", {}).get("initial_peers", [])
        or world_data.get("world", {}).get("genre_contract", {}).get("competition", {}).get("initial_peers", [])
    )

    if not peers:
        print("  [skip] No initial_peers found in world.yaml")
        return

    conn = sqlite3.connect(str(db_path))
    conn.isolation_level = None  # autocommit to ensure persistence on Google Drive
    cursor = conn.cursor()

    campaign_id = save_dir.name

    # Ensure entities table exists with correct schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            campaign_id TEXT,
            entity_type TEXT,
            entity_id TEXT,
            state_json TEXT,
            PRIMARY KEY (campaign_id, entity_type, entity_id)
        )
    """)
    conn.commit()

    # Check existing count
    cursor.execute(
        "SELECT COUNT(*) FROM entities WHERE campaign_id = ? AND entity_type = 'peer_players'",
        (campaign_id,),
    )
    existing = cursor.fetchone()[0]

    if existing >= len(peers):
        print(f"  Peers already initialized ({existing} found), skipping")
        conn.close()
        return

    # Clear old data and re-insert
    cursor.execute(
        "DELETE FROM entities WHERE campaign_id = ? AND entity_type = 'peer_players'",
        (campaign_id,),
    )

    for peer in peers:
        agent_data = {
            "id": peer["id"], "name": peer["name"],
            "profession": "survivalist", "level": 1,
            "location_id": "starting_area", "hp": 100.0,
            "attributes": {"strength": 14.0, "agility": 14.0, "spirit": 14.0, "constitution": 13.0},
            "action_history": [],
            "score_components": {"combat": 0.0, "resources": 0.0, "base": 0.0, "information": 0.0, "social": 0.0},
            "ranking_percentile": 50.0,
        }
        cursor.execute(
            "INSERT OR REPLACE INTO entities (campaign_id, entity_type, entity_id, state_json) VALUES (?, ?, ?, ?)",
            (campaign_id, "peer_players", peer["id"], json.dumps(agent_data, ensure_ascii=False))
        )

    conn.commit()
    conn.close()
    print(f"  Peer players: {len(peers)} entities initialized in SQLite")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def migrate_save(save_path_str: str):
    save_dir = Path(save_path_str)

    if not save_dir.exists():
        print(f"Error: Save directory not found: {save_dir}")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"Migrating: {save_dir.name}")
    print(f"{'='*60}")

    # Step 1: Backup
    print("\n[1/5] Creating backup...")
    step_backup(save_dir)

    # Step 2: Fix ranking
    print("\n[2/5] Fixing ranking state...")
    step_fix_ranking(save_dir)

    # Step 3: Archive channel messages
    print("\n[3/5] Archiving channel messages...")
    step_archive_channel(save_dir)

    # Step 4: Fix rival state
    print("\n[4/5] Fixing rival state...")
    step_fix_rival(save_dir)

    # Step 5: Initialize peer players
    print("\n[5/5] Initializing peer players in SQLite...")
    step_init_peers(save_dir)

    print(f"\n{'='*60}")
    print("Migration complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python tools/migrate_survival_save.py <save_directory>")
        print("Example: python tools/migrate_survival_save.py saves/灰烬列车")
        sys.exit(1)

    migrate_save(sys.argv[1])
