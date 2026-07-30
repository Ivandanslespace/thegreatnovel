#!/usr/bin/env python3
"""Fix compiler_version mismatch in SQLite snapshot."""
import sqlite3
import json
import sys
from pathlib import Path

db_path = Path("saves/锈铁方舟/campaign.sqlite3")
conn = sqlite3.connect(str(db_path))
cur = conn.cursor()

# Check schema
cur.execute("PRAGMA table_info(snapshots)")
cols = cur.fetchall()
print("snapshots columns:", cols)

cur.execute("SELECT sql FROM sqlite_master WHERE name='snapshots'")
print("schema:", cur.fetchone())

# Find the key column name
key_col = None
for col in cols:
    if col[1] in ('key', 'name', 'snapshot_key'):
        key_col = col[1]
        break
if not key_col:
    key_col = cols[0][1]  # first column as fallback

print(f"Using key column: {key_col}")

# Read current world snapshot
cur.execute(f"SELECT rowid, data FROM snapshots WHERE {key_col}='world'")
row = cur.fetchone()
if not row:
    print("No world snapshot found, trying all rows...")
    cur.execute(f"SELECT rowid, {key_col}, substr(data,1,100) FROM snapshots")
    for r in cur.fetchall():
        print(f"  rowid={r[0]}, key={r[1]}, preview={r[2]}")
    sys.exit(1)

snap_id, raw = row
data = json.loads(raw)
old_ver = data.get("generation_bundle", {}).get("compiler_version", "N/A")
print(f"Old compiler_version: {old_ver}")

# Update
if "generation_bundle" in data:
    data["generation_bundle"]["compiler_version"] = "2.0"

cur.execute("UPDATE snapshots SET data=? WHERE rowid=?", (json.dumps(data, ensure_ascii=False), snap_id))
conn.commit()
print(f"Updated to 2.0")

conn.close()
print("Done")
