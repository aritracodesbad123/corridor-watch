-- Sprint 1 reliability. Also applied by db.init_schema() via PLATFORM_SCHEMA / _ensure_columns.
-- Backward compatible: identity columns are nullable; unique index is partial.

CREATE TABLE IF NOT EXISTS outbox_events (
    outbox_id TEXT PRIMARY KEY,
    event_type TEXT,
    payload TEXT,
    created_at TEXT,
    published_at TEXT,
    attempts INTEGER,
    last_error TEXT
);

-- Existing ingestion_events rows may have NULL identity. Do not add a full UNIQUE(source_system, source_event_id).
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingest_source_event
    ON ingestion_events(source_system, source_event_id)
    WHERE source_event_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished
    ON outbox_events(published_at, created_at);
