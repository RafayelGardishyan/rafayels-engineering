---
id: KNW-0001
title: "Case-Based Reasoning memory layer for Claude plugins"
type: knowledge
problem_type: best_practice
confidence: established
applies_when: "Building a Claude Code plugin that needs to learn from user feedback and past workflow runs without editing agent/skill files directly"
guidance: "Use a local sqlite-vec + fastembed case bank with workflow hooks for retrieval, capture, and signal emission. Keep agents frozen. Improvement flows through retrieval, not self-editing. Pattern detection generates reviewable draft PRs with strict guardrails."
scope: [architecture, memory, cbr, claude-plugins, python, sqlite-vec, fastembed]
related: []
supersedes: []
last_validated: 2026-04-10
---

# Case-Based Reasoning Memory Layer for Claude Plugins

## Problem

The rafayels-engineering plugin had **zero memory between sessions**. Each `/re:feature` run started cold. The `compound-docs` skill captured solved problems as markdown files, but the loop was broken:

- Nothing tracked whether documented solutions *actually worked* when retrieved later
- Retrieval was keyword-based (ripgrep), not semantic
- Cases were referenced only on explicit request via `learnings-researcher`, never injected into active workflows at runtime
- No feedback signal to distinguish successful patterns from failed ones
- Learnings didn't compound across projects (everything was project-scoped markdown)

We wanted the plugin to *learn from use over time* — Memento (arXiv 2508.16153) proved case-based reasoning with retrieval beats prompt rewriting for continual agent improvement (87.9% GAIA benchmark). We wanted that benefit without the risks of self-editing agent prompts.

## Root Cause

Three orthogonal gaps in the existing infrastructure:

1. **No feedback signal loop** — the `compound-docs` skill wrote markdown but had no mechanism to label cases as successful or failed based on downstream outcomes.
2. **No vector-based retrieval** — without semantic similarity search, the plugin couldn't efficiently find relevant past cases for a new feature description.
3. **No runtime injection** — even if cases were retrieved, there were no hooks in active workflows to inject them into agent context at decision points.

## Solution

Two-skill architecture with complete separation between memory storage/retrieval and pattern-proposal. All agents stay frozen — improvement flows through **retrieval**, not self-editing.

### Architecture

```
┌────────────────────────────────────────────────┐
│ skills/memory/                                 │
│ - 7 Python modules + CLI entry                 │
│ - sqlite-vec + fastembed (BGE-small)           │
│ - 18 subcommands, --json on all                │
│ - SQL-level invariants (CHECK, triggers, FKs)  │
└────────────────────────────────────────────────┘
                    │
                    │ workflow hooks (retrieve + capture + signal)
                    ▼
┌────────────────────────────────────────────────┐
│ /workflows:brainstorm                          │
│ /workflows:plan                                │
│ /workflows:work                                │
│ /workflows:review                              │
│ /workflows:compound                            │
│ /re:feature Phase 10 (final merge signal)      │
└────────────────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│ skills/memory-proposer/                        │
│ - scipy UPGMA clustering (threshold 0.15)      │
│ - Draft PR generation via git worktree + gh    │
│ - Guardrails: refuses agents/, draft-only      │
│ - Depends on memory skill (sibling Python import)
└────────────────────────────────────────────────┘
                    │
                    ▼
┌────────────────────────────────────────────────┐
│ /re:memory-review — interactive audit command  │
└────────────────────────────────────────────────┘
```

### Key Design Decisions (Why These Choices)

**Frozen agents, retrieval-only improvement**
Memento's central insight: self-editing prompts causes silent regressions, drift, and plugin incoherence. Retrieval is the opposite — every injected case is visible, attributable, and can be excluded. Pattern detection in `memory-proposer` generates *reviewable draft PRs*, never mutates files autonomously.

**`cases_raw` + `cases_vec` split table pattern**
sqlite-vec 0.x cannot `ALTER` vec0 virtual tables. We keep the source of truth in a plain SQL table (`cases_raw`) and use vec0 (`cases_vec`) as a disposable index. Model upgrades re-embed from plain text without re-running inference on the original content, and schema migrations drop+rebuild vec0 without losing data.

**`PARTITION KEY phase` on vec0**
Pre-filters the vector index by phase before distance calculation. With 5-6 phases and ~2000 cases, each query scans ~400 vectors instead of 2000. Single biggest performance optimization.

**Quarantine-on-write + SQL trigger**
New cases start in `status='quarantine'` and are not retrievable. A SQL trigger promotes them to `status='active'` when they accumulate 2+ positive signals. The invariant is enforced in the database, not Python — a crashed or buggy Python caller cannot violate it.

**MMR reranking with λ=0.5**
Top-10 candidates from sqlite-vec get MMR-reranked to K=3 for diversity. Prevents three near-duplicate past cases from eating the entire token budget.

**Exponential reward decay at retrieval time**
`effective_reward = stored_reward * exp(-age_days / 60)`. Older cases trusted less without being deleted. Promoted cases exempt. Applied at retrieval, not storage — the original reward stays in the DB.

**Cold-start skip**
Retrieval is skipped entirely until per-phase bank has `k*3` active cases. Prevents noisy injection from a nearly-empty bank during bootstrap.

**Composite reward formula (pure function)**
```python
WEIGHTS = {"merge": 0.40, "approval": 0.30, "review": 0.20, "regression": 0.10}

def composite_reward(signals: list[tuple[str, float]]) -> float:
    """Weighted mean of signals by type, mapped [-1,1] → [0,1]. Neutral = 0.5."""
    if not signals:
        return 0.5
    by_type = group_by_type(signals)
    numerator = sum(WEIGHTS[t] * mean(values) for t, values in by_type.items())
    denominator = sum(WEIGHTS[t] for t in by_type)
    return clamp((numerator / denominator + 1.0) / 2.0, 0.0, 1.0)
```

Pure function — trivially unit-testable without DB. The wrapper `composite_reward_for_case(conn, case_id)` does the fetch.

**Separate `memory-proposer` skill for auto-PR generation**
The memory system editing its own plugin's source files is a genuine *layering inversion*. We isolated the PR-generation logic into `skills/memory-proposer/` (separate from `skills/memory/`) to make the inversion structurally visible and removable. Guardrails:
- Always creates draft PRs
- Only appends to `## Learned Patterns` sections in `skills/` or `references/`
- Refuses any path under `agents/` (system prompts stay human-authored)
- Content-hash branch names for idempotency
- Triple marker: draft + `learned-pattern` label + HTML body comment

**Offline-first with graceful degradation**
No cloud API calls. fastembed BGE-small model cached in `~/.cache/rafayels-memory/fastembed/`. If fastembed or sqlite-vec are missing, workflows proceed without memory injection (exit code 75 / `EX_TEMPFAIL`). The feature is opt-in; the plugin is fully functional without it.

### Integration Pattern (Workflow Hooks)

All 5 workflow commands got three types of hooks:

1. **Retrieve** (at phase start):
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory.py query \
     "<query>" --phase <phase> --k 3 --format md 2>/dev/null
   ```
2. **Capture** (at phase completion):
   ```bash
   memory write --phase <phase> --query "..." --plan "..." --outcome "..." --json
   ```
3. **Signal** (at event moments):
   ```bash
   memory signal <case_id> <type> <value> --source "..."
   ```

Exit code 75 means "memory unavailable" — workflows treat it as a graceful no-op, not an error.

## Prevention

This is a new feature, not a bug, but there are generalizable patterns worth extracting:

### When to Use This Pattern

**Use CBR memory** when:
- Your system makes repeated similar decisions over time
- You have a stable evaluation signal (merge, CI, review, user approval)
- You want improvement without retraining or editing prompts
- You need offline-first operation

**Don't use CBR memory** when:
- Decisions are mostly one-off with no useful similarity structure
- You have no reliable reward signal (avoid case bank poisoning)
- Your system already has a learned component that handles the same job
- Context window budget is tight (retrieved cases compete with other content)

### Gotchas We Hit (and Fixed)

1. **sqlite-vec 0.x schema instability** → pin exactly (`==0.1.7`), use the `cases_raw` + `cases_vec` split so migrations can drop+rebuild vec0 without data loss.

2. **`PRAGMA foreign_keys=ON` default is OFF in SQLite** → set explicitly on every connection. Without it, `ON DELETE CASCADE` silently doesn't fire.

3. **`sys.exit(0)` on dependency failure is the wrong signal** → workflows piping the output get empty stdout and proceed thinking it succeeded. Use exit 75 (`os.EX_TEMPFAIL`) and document workflow hooks to tolerate it.

4. **BGE-small cosine distances are compressed** → clustering threshold of 0.25 produces topical blobs, not pattern clusters. Use 0.15 for BGE-small. Empirical distribution: near-duplicates 0.05–0.12, same-topic 0.12–0.20, loosely related 0.20–0.35.

5. **scipy `method='ward'` on cosine distances is silently wrong** → ward requires Euclidean. Use `method='average'` (UPGMA) for cosine.

6. **Cluster IDs are unstable across re-clustering runs** → don't persist IDs, persist centroids. Match new clusters to existing patterns by centroid cosine similarity.

7. **Daemon spawn races** → PID file + `fcntl.flock` exclusive non-blocking lock. Second daemon sees locked PID file and exits 0 silently.

8. **`memory-embedd.py` with a hyphen breaks Python imports** → rename to `embed_daemon.py`. Hyphens work in subprocess spawn but not in `from X import Y`.

9. **BEGIN IMMEDIATE for writes avoids deferred→upgrade deadlocks** → `SQLITE_BUSY_SNAPSHOT` from a deferred transaction upgrading mid-flight isn't resolved by `busy_timeout`. Take the writer lock up front.

### Architecture Review Patterns

From the architecture reviewer's feedback during the plan review:

- **Separate frozen artifacts from the learned layer** (Memento's core insight)
- **Enforce invariants in the schema, not in Python** (CHECK constraints + triggers)
- **Typed config loader, not stringly-typed KV** (catch mismatches at startup)
- **Dependency injection over module globals** (every function takes `conn` explicitly)
- **Pure function cores for testability** (extract `composite_reward(signals)` as pure)
- **Extract protocol/interface before concrete implementation** (`VectorIndex` protocol)

## References

### Internal
- Brainstorm: `docs/brainstorms/2026-04-10-self-improving-plugin-brainstorm.md`
- Plan: `docs/plans/2026-04-10-feat-self-improving-plugin-memory-layer-plan.md`
- PR: [#2](https://github.com/RafayelGardishyan/rafayels-engineering/pull/2)
- Skills: `skills/memory/SKILL.md`, `skills/memory-proposer/SKILL.md`
- Schema reference: `skills/memory/references/schema.md`
- Signals reference: `skills/memory/references/signals.md`

### External
- Memento paper: https://arxiv.org/abs/2508.16153
- Memento repo: https://github.com/Agent-on-the-Fly/Memento
- sqlite-vec: https://github.com/asg017/sqlite-vec
- fastembed: https://github.com/qdrant/fastembed
- BGE-small: https://huggingface.co/BAAI/bge-small-en-v1.5
- MMR original paper (Carbonell & Goldstein 1998): https://www.cs.cmu.edu/~jgc/publication/The_Use_MMR_Diversity_Based_LTMIR_1998.pdf
- A-MemGuard (memory poisoning defense): https://www.arxiv.org/pdf/2510.02373
- Reflexion (verbal RL): https://arxiv.org/abs/2303.11366

### Related Patterns Considered (rejected)
- **Voyager** (skill library of code snippets) — too close to self-editing
- **LanceDB + sentence-transformers** — heavier deps than sqlite-vec + fastembed
- **Self-editing agent prompts** — high risk of silent regressions, violates Memento's empirical finding
- **Pure markdown + ripgrep** — contradicts the requirement for semantic retrieval
