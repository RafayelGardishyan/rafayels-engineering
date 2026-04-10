# Memory DB Schema Reference

Schema v1 — see `scripts/migrations/001_initial.sql` for canonical definition.

## Tables

### `meta` — key-value configuration

| Column | Type | Notes |
|---|---|---|
| `key` | TEXT PRIMARY KEY | `schema_version`, `embedding_model`, `embedding_dim` |
| `value` | TEXT NOT NULL | String-encoded value |

### `cases_raw` — source of truth

Plain SQL table holding all case metadata and text content. Independent of
vec0 so model upgrades can re-embed from `query`+`plan` without touching vec0.

| Column | Type | Notes |
|---|---|---|
| `case_id` | INTEGER PK | autoincrement |
| `phase` | TEXT | CHECK in (brainstorm, plan, work, review, compound, other) |
| `case_type` | TEXT | bug / pattern / decision / solution |
| `status` | TEXT | quarantine / active / archived / promoted |
| `reward` | REAL | CHECK 0.0..1.0, recomputed by trigger on signal insert |
| `created`, `updated` | INTEGER | unix timestamp |
| `project` | TEXT | repo basename (auto-detected via git) |
| `title`, `query`, `plan`, `trajectory`, `outcome` | TEXT | human-readable fields |
| `tags` | TEXT | JSON array |
| `injection_summary` | TEXT | pre-computed ~300-token summary for LLM context |

### `cases_vec` — vector index (sqlite-vec vec0)

| Column | Notes |
|---|---|
| `case_id` | PK, foreign reference to cases_raw |
| `phase` | **PARTITION KEY** — pre-filters before distance calc |
| `embedding` | float[384] cosine distance |

### `signals` — append-only feedback ledger

| Column | Type | Notes |
|---|---|---|
| `signal_id` | INTEGER PK | autoincrement |
| `case_id` | INTEGER | FK ON DELETE CASCADE |
| `signal_type` | TEXT | CHECK in (merge, ci, approval, review, regression) |
| `value` | REAL | CHECK -1.0..1.0 |
| `source` | TEXT | e.g. "pr:#123", "phase:plan" |
| `created` | INTEGER | unix timestamp |
| `metadata` | TEXT | JSON |

### `retrievals` — audit log

| Column | Notes |
|---|---|
| `retrieval_id` | PK |
| `case_id` | FK CASCADE |
| `phase`, `workflow_run_id`, `distance`, `rank`, `created` | metadata |

Used by `retrieval_cap_penalty()` to demote over-retrieved cases.

### `case_links` — graph of related cases

Canonical order (`case_id_a < case_id_b`) enforced via CHECK.

### `patterns` — detected clusters (used by memory-proposer)

| Column | Notes |
|---|---|
| `pattern_id` | PK |
| `centroid` | BLOB (384 float32 = 1536 bytes, CHECK enforced) |
| `case_ids` | JSON array |
| `case_count`, `avg_reward`, `summary` | cluster metadata |
| `pr_url`, `pr_branch`, `status` | proposal state |

## Triggers

### `promote_on_positive_signals`
Fires AFTER INSERT on signals WHEN NEW.value > 0. Promotes case from
`quarantine` to `active` when it has 2+ positive signals. Enforces the
quarantine-on-write poisoning defense in SQL, not Python.

### `recompute_reward_on_signal`
Fires AFTER INSERT on signals. Recomputes `cases_raw.reward` as a
weighted average of signal values by type (weights: merge=0.4, approval=0.3,
review=0.2, regression=0.1), mapped from [-1,1] to [0,1].

## PRAGMAs

Required on every connection:
- `foreign_keys=ON` (FK CASCADE depends on this)
- `journal_mode=WAL`
- `synchronous=NORMAL`
- `busy_timeout=30000`
- `mmap_size=268435456`
- `cache_size=-65536`

## Write Pattern

All writes use `BEGIN IMMEDIATE` to acquire the writer lock up front. Avoids
`SQLITE_BUSY_SNAPSHOT` from deferred transaction upgrades.
