---
date: 2026-04-10
topic: self-improving-plugin
inspiration: Memento-Teams/Memento (arXiv 2508.16153)
---

# Self-Improving Plugin: Case-Based Learning Layer

## What We're Building

A retrieval-based learning layer for the rafayels-engineering plugin. The plugin captures feedback signals from every workflow run, stores them as cases in a local vector database, and injects relevant past cases into active agents at runtime. Over time, the plugin gets better at planning, reviewing, and implementing features — without ever editing its own agent or skill files.

**Key design constraint:** Agents and skills stay frozen. All improvement flows through retrieval, not self-editing. This preserves plugin coherence and makes every learning gain reviewable.

## Why This Approach

Memento (the inspiration) proved that case-based reasoning beats prompt rewriting for continual learning: 87.9% on GAIA by keeping agents frozen and learning through retrieval only. Self-editing prompts is high-risk — silent regressions, drift, loss of coherence. Retrieval is the opposite: every injected case is visible, attributable, and can be excluded.

The plugin already has 90% of the capture infrastructure (compound-docs skill, learnings-researcher agent, docs/solutions/ schema). What's missing is (a) a feedback signal that tells us which cases actually worked, (b) a vector-based retrieval layer, and (c) injection points inside active workflows.

Approach B (pure markdown + ripgrep) was rejected because it contradicts the explicit requirement for vector retrieval with local embeddings.

## Key Decisions

- **Storage: sqlite-vec + fastembed (offline-first)** — SQLite extension for vector search, fastembed (ONNX) for on-machine embeddings with BAAI/bge-small-en-v1.5 (384-dim). **Hard constraint: no cloud API calls for embeddings or retrieval.** Runs fully offline. User-scope DB at `~/.claude/plugins/rafayels-engineering/memory.db` so learning is cross-project. Graceful degradation: if fastembed or sqlite-vec fail to load, the memory layer is disabled silently (zero-cost skip) and workflows proceed without case injection.

- **Python sidecar at `skills/memory/scripts/`** — CLI commands (`memory write`, `memory query`, `memory signals`, `memory report`) callable from any workflow. Follows the ralph-lauren precedent for Python-in-plugin.

- **Multi-signal composite reward** — Cases are scored by combining: merged PR + CI pass (weight 0.4), explicit user approval at phase handoffs (weight 0.3), review findings severity (weight 0.2), regression signal (weight 0.1). Regression signal fires if a file touched by the case gets reverted, or gets a new bug-track entry within 30 days. In-process signals aggregate as the pipeline runs — no case waits for final merge.

- **In-process signal capture** — Signals are generated *during* the workflow, not just at the end. Brainstorm captures iteration count + approval. Plan captures deepen/edit activity. Work captures test pass rate + error recovery + interrupts. Review captures P1/P2/P3 counts + reviewer agreement. Compound captures whether the problem got documented. This way, abandoned workflows still produce useful partial signals.

- **Per-phase injection budget K=3** — Each phase retrieves up to 3 relevant cases, deduplicated across phases (total ~12 per pipeline run max). Prevents context bloat. Retrieval is semantic (embedding similarity) scoped to phase-relevant case types. **Each case is capped at ~300 tokens** (summary + key fields only — full trajectories stay in the DB for audit but never hit the LLM context).

- **Injection everywhere /re:feature touches** — Brainstorm, plan, work, review, compound, docs. Cases flow into every decision point, but with strict per-phase budgets.

- **Pragmatic auto-capture with audit command** — Cases auto-capture with signals. New `/re:memory-review` command audits the bank, prunes low-value cases, flags outliers. Low-score cases auto-archive after 90 days. Manual promotion keeps critical patterns permanent.

- **Retrieval + auto-generated PR suggestions (no direct self-editing)** — When N similar cases emerge around a pattern, a scheduled command generates a PR proposing skill/agent updates. Human reviews like any code change. Plugin never writes to agents/ or skills/ directly.

## Open Questions

- **Embedding model warmup**: First run will download the fastembed model (~50MB). Should we ship an install script, require explicit opt-in, or auto-download on first use?
- **DB migration strategy**: How do we handle schema changes to the case bank once users have data? Suggest: migrations in `skills/memory/scripts/migrations/`.
- **Cross-project namespacing**: User-scope DB is shared across repos. Do we tag cases with project/repo ID for filtering, or let the embedding similarity handle relevance naturally?
- **Case TTL vs. soft decay**: Should cases decay gradually (weight reduction over time) or hard-expire after 90 days? Memento doesn't decay — cases just accumulate.
- **Bootstrap problem**: The bank is empty on day one. Should we seed it from existing docs/solutions/ content, or start fresh?
- **Pattern detection threshold**: At what count of similar cases does the system auto-generate a skill-update PR? 5? 10? Configurable?

## Next Steps

→ `/workflows:plan` for implementation details
