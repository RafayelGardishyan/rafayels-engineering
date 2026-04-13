-- Memory layer schema v1
-- Run by db.init_schema() on first invocation.

-- 0. Metadata: schema version, embedding model, settings
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Seed required metadata
INSERT OR IGNORE INTO meta (key, value) VALUES
    ('schema_version', '1'),
    ('embedding_model', 'BAAI/bge-small-en-v1.5'),
    ('embedding_dim', '384');

-- 1. Source of truth: plain table with full case data
CREATE TABLE IF NOT EXISTS cases_raw (
    case_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    phase             TEXT NOT NULL
        CHECK(phase IN ('brainstorm','plan','work','review','compound','other')),
    case_type         TEXT
        CHECK(case_type IS NULL OR case_type IN ('bug','pattern','decision','solution')),
    status            TEXT NOT NULL DEFAULT 'quarantine'
        CHECK(status IN ('quarantine','active','archived','promoted')),
    reward            REAL NOT NULL DEFAULT 0.5
        CHECK(reward >= 0.0 AND reward <= 1.0),
    created           INTEGER NOT NULL,
    updated           INTEGER NOT NULL,
    project           TEXT,
    title             TEXT,
    query             TEXT NOT NULL,
    plan              TEXT,
    trajectory        TEXT,
    outcome           TEXT,
    tags              TEXT,
    injection_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_cases_phase  ON cases_raw(phase);
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases_raw(status);
CREATE INDEX IF NOT EXISTS idx_cases_status_reward ON cases_raw(status, reward);
CREATE INDEX IF NOT EXISTS idx_cases_project ON cases_raw(project);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases_raw(created);

-- 2. Vector index (sqlite-vec vec0 virtual table)
-- PARTITION KEY on phase pre-filters the index before distance calculation.
-- Note: created by db.init_schema() AFTER sqlite_vec is loaded, because
-- this is a virtual table that requires the extension.
-- See db.py::_create_vec_table().

-- 3. Signals ledger (append-only)
CREATE TABLE IF NOT EXISTS signals (
    signal_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL,
    signal_type TEXT NOT NULL
        CHECK(signal_type IN ('merge','ci','approval','review','regression')),
    value       REAL NOT NULL
        CHECK(value >= -1.0 AND value <= 1.0),
    source      TEXT,
    created     INTEGER NOT NULL,
    metadata    TEXT,
    FOREIGN KEY (case_id) REFERENCES cases_raw(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_signals_case ON signals(case_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type);

-- 4. Retrieval audit log (for cap-per-case poisoning defense + debugging)
CREATE TABLE IF NOT EXISTS retrievals (
    retrieval_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id          INTEGER NOT NULL,
    phase            TEXT NOT NULL,
    workflow_run_id  TEXT,
    distance         REAL,
    rank             INTEGER,
    created          INTEGER NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases_raw(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_retrievals_case         ON retrievals(case_id);
CREATE INDEX IF NOT EXISTS idx_retrievals_case_created ON retrievals(case_id, created);
CREATE INDEX IF NOT EXISTS idx_retrievals_run          ON retrievals(workflow_run_id);

-- 5. Case links (bidirectional graph; used by `memory link`)
CREATE TABLE IF NOT EXISTS case_links (
    case_id_a INTEGER NOT NULL,
    case_id_b INTEGER NOT NULL,
    link_type TEXT NOT NULL DEFAULT 'related',
    created   INTEGER NOT NULL,
    PRIMARY KEY (case_id_a, case_id_b, link_type),
    FOREIGN KEY (case_id_a) REFERENCES cases_raw(case_id) ON DELETE CASCADE,
    FOREIGN KEY (case_id_b) REFERENCES cases_raw(case_id) ON DELETE CASCADE,
    CHECK(case_id_a < case_id_b)  -- canonical order to prevent dup edges
);

-- 6. Pattern state (Phase 5: used by memory-proposer skill)
CREATE TABLE IF NOT EXISTS patterns (
    pattern_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    centroid    BLOB NOT NULL
        CHECK(length(centroid) = 1536),  -- 384 floats * 4 bytes
    case_ids    TEXT NOT NULL,
    case_count  INTEGER NOT NULL,
    avg_reward  REAL NOT NULL,
    summary     TEXT,
    pr_url      TEXT,
    pr_branch   TEXT,
    status      TEXT NOT NULL DEFAULT 'detected'
        CHECK(status IN ('detected','proposed','merged','ignored')),
    created     INTEGER NOT NULL,
    updated     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_patterns_status ON patterns(status);

-- Triggers

-- Promote quarantined cases to 'active' when they accumulate 2+ positive signals.
-- This is the quarantine-on-write poisoning defense, enforced in SQL not Python.
CREATE TRIGGER IF NOT EXISTS promote_on_positive_signals
AFTER INSERT ON signals
WHEN NEW.value > 0
BEGIN
    UPDATE cases_raw
    SET status = 'active',
        updated = strftime('%s', 'now')
    WHERE case_id = NEW.case_id
      AND status = 'quarantine'
      AND (SELECT COUNT(*) FROM signals
           WHERE case_id = NEW.case_id AND value > 0) >= 2;
END;

-- Recompute reward whenever a signal is inserted for a case.
-- Formula matches capture.composite_reward() — this is a DB-side safety net
-- that keeps cases_raw.reward in sync even if the Python layer crashes
-- between signal insert and reward update.
CREATE TRIGGER IF NOT EXISTS recompute_reward_on_signal
AFTER INSERT ON signals
BEGIN
    UPDATE cases_raw
    SET reward = MAX(0.0, MIN(1.0, (
        -- weighted mean of signal type means, mapped [-1,1] -> [0,1]
        (
            COALESCE(0.40 * (SELECT AVG(value) FROM signals WHERE case_id = NEW.case_id AND signal_type = 'merge'), 0)
          + COALESCE(0.30 * (SELECT AVG(value) FROM signals WHERE case_id = NEW.case_id AND signal_type = 'approval'), 0)
          + COALESCE(0.20 * (SELECT AVG(value) FROM signals WHERE case_id = NEW.case_id AND signal_type = 'review'), 0)
          + COALESCE(0.10 * (SELECT AVG(value) FROM signals WHERE case_id = NEW.case_id AND signal_type = 'regression'), 0)
        ) / MAX(1, (
            CASE WHEN EXISTS (SELECT 1 FROM signals WHERE case_id = NEW.case_id AND signal_type = 'merge') THEN 0.40 ELSE 0 END
          + CASE WHEN EXISTS (SELECT 1 FROM signals WHERE case_id = NEW.case_id AND signal_type = 'approval') THEN 0.30 ELSE 0 END
          + CASE WHEN EXISTS (SELECT 1 FROM signals WHERE case_id = NEW.case_id AND signal_type = 'review') THEN 0.20 ELSE 0 END
          + CASE WHEN EXISTS (SELECT 1 FROM signals WHERE case_id = NEW.case_id AND signal_type = 'regression') THEN 0.10 ELSE 0 END
        ))
        + 1.0
    ) / 2.0))
    WHERE case_id = NEW.case_id;
END;
