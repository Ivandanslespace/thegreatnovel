"""Schema migration 4: independently executable SQL."""

SQL = r"""
ALTER TABLE drafts ADD COLUMN validation_run_id TEXT;
ALTER TABLE validation_reports ADD COLUMN run_id TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS idx_validation_run
ON validation_reports(draft_id, run_id, validator);
"""



__all__ = ["SQL"]
