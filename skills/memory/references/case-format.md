# Case Format & Injection Budget

## Case Fields

| Field | Purpose |
|---|---|
| `query` | What the user was trying to do (embedded for retrieval) |
| `plan` | The approach taken (embedded alongside query) |
| `trajectory` | JSON string: key actions/decisions (not embedded, stored for audit) |
| `outcome` | What happened (stored, shown in injection) |
| `title` | Short human-readable label |
| `tags` | JSON array for filtering |
| `injection_summary` | Pre-computed ~300-token summary for LLM context |

## Embedding Text

The text used to generate the embedding is:

```
{query}\n\n{plan}
```

This balances "what the user wanted" and "how we approached it" — the two
components that matter for retrieval similarity.

## Injection Summary (the 300-token cap)

`injection_summary` is pre-computed at write time and stored. It's what gets
injected into LLM context, not the full case. Structure:

```
**{title}**
Query: {query}
Approach: {plan}
Outcome: {outcome}
```

Capped at ~300 tokens via `enforce_token_cap()`:
- Uses tiktoken (`cl100k_base` encoding) if installed — accurate.
- Falls back to word-count estimate (1 word ≈ 1.3 tokens) if tiktoken missing.
- Prefers sentence boundaries when truncating.

## Positive vs Negative Injection Format

Retrieved cases are rendered with asymmetric framing:

### Positive (reward > 0.5) — "imitate the approach"

```markdown
### Past Successes (imitate the approach)
- **Case #42** [reward=0.85, status=active]
  **Set up marketplace sync**
  Query: How to sync plugin files to marketplace repo?
  Approach: rsync -a --delete from dev to marketplace repo
  Outcome: Clean one-way mirror, idempotent
```

### Negative (reward <= 0.5) — "avoid these mistakes"

```markdown
### Past Failures (avoid these mistakes)
- **Case #17** [reward=0.25]: Tried to use git subtree for marketplace
  → Why it failed: Merge conflicts every sync, hard to revert
```

Negative cases are rendered shorter — they're warnings, not templates.

## Budget per Retrieval

- **K=3 cases per phase** (tunable)
- **Top-10 candidates fetched**, MMR-reranked to K=3
- **~300 tokens per case** × 3 cases = ~900 tokens per phase
- **Per-phase dedup** via `--exclude` prevents double-injection across phases
- **Total per `/re:feature` run**: ~900 tokens × 5 phases = ~4500 tokens max

This is a predictable, bounded cost — not dependent on case bank size.
