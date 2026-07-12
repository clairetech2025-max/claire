-- CLAIRE Venture Intelligence metadata schema.
-- ARE Truth Spine remains authority. These tables store downstream metadata
-- and append-only ledger references to Truth Spine hashes.

CREATE TABLE IF NOT EXISTS admitted_evidence (
    are_hash TEXT PRIMARY KEY,
    checksum TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    collector TEXT NOT NULL,
    plane TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    precision DOUBLE PRECISION NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    provenance_url TEXT NOT NULL DEFAULT '',
    entity_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    admitted_at DOUBLE PRECISION NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_admitted_evidence_plane ON admitted_evidence(plane);
CREATE INDEX IF NOT EXISTS idx_admitted_evidence_collector ON admitted_evidence(collector);
CREATE INDEX IF NOT EXISTS idx_admitted_evidence_source ON admitted_evidence(source);

CREATE TABLE IF NOT EXISTS collector_state (
    collector TEXT PRIMARY KEY,
    last_cursor TEXT,
    last_run_at DOUBLE PRECISION,
    status TEXT NOT NULL,
    error_json JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS collector_runs (
    run_id TEXT PRIMARY KEY,
    collector TEXT NOT NULL,
    admitted_count INTEGER NOT NULL,
    error_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    next_cursor TEXT,
    started_at DOUBLE PRECISION NOT NULL,
    finished_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS admission_claims (
    content_hash TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    are_hash TEXT NOT NULL DEFAULT '',
    updated_at DOUBLE PRECISION NOT NULL,
    last_error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS reconciliation_state (
    name TEXT PRIMARY KEY,
    last_sequence BIGINT NOT NULL DEFAULT 0,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_events (
    ledger_seq BIGSERIAL UNIQUE,
    event_id TEXT PRIMARY KEY,
    opportunity_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    truth_hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL DEFAULT '0',
    event_hash TEXT NOT NULL DEFAULT '',
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_opportunity_events_opportunity
    ON opportunity_events(opportunity_id, ledger_seq);

CREATE INDEX IF NOT EXISTS idx_opportunity_events_ledger_seq
    ON opportunity_events(ledger_seq);

CREATE TABLE IF NOT EXISTS projection_events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    truth_hash TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL
);
