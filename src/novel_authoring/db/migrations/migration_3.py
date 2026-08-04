"""Schema migration 3: independently executable SQL."""

SQL = r"""
ALTER TABLE drafts ADD COLUMN task_id TEXT;
ALTER TABLE drafts ADD COLUMN chapter_title TEXT NOT NULL DEFAULT '';
ALTER TABLE drafts ADD COLUMN output_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE drafts ADD COLUMN base_event_seq INTEGER NOT NULL DEFAULT 0;
ALTER TABLE drafts ADD COLUMN base_projection_hash TEXT NOT NULL DEFAULT '';
"""



__all__ = ["SQL"]
