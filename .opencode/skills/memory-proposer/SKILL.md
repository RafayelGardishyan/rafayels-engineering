---
name: memory-proposer
description: "Detects emerging patterns in the memory case bank and proposes skill updates as reviewable draft PRs. Depends on the `memory` skill. Use when the user wants to surface recurring successful patterns and optionally encode them into skill files."
---

# Memory Proposer

Sibling skill to `memory`. Detects recurring patterns across successful cases
in the memory bank and generates draft PRs that append learned patterns to
skill files.

**Architectural note**: This is a genuine layering inversion (the memory
system edits its own plugin's source files). It lives in its own skill
— separate from `memory` — to make the inversion structurally visible
and isolable. The `memory` skill itself never edits agent or skill files.

## Quick Start

```bash
# Detect pattern clusters in the memory bank
python3 ${OPENCODE_PLUGIN_ROOT}/skills/memory-proposer/scripts/memory_proposer.py detect

# List all detected patterns
python3 ${OPENCODE_PLUGIN_ROOT}/skills/memory-proposer/scripts/memory_proposer.py list

# Generate a draft PR for a specific pattern
python3 ${OPENCODE_PLUGIN_ROOT}/skills/memory-proposer/scripts/memory_proposer.py \
  propose 42 --target-skill github
```

## Safety Guardrails

1. **Always draft PRs** — never merges automatically. `--draft` flag enforced.
2. **Triple marker** — draft status + `automated,learned-pattern` label + HTML
   body comment `<!-- generated-by: memory-pattern-detector v1 -->`. Humans,
   tooling, and PR filters all recognize the origin.
3. **Only appends to `## Learned Patterns`** sections in skills or references.
   Creates the section if missing; never modifies existing content.
4. **Refuses `agents/`** — the edit function raises `ProposeError` if asked
   to touch any file under `agents/`. System prompts stay human-authored.
5. **Content-hash branch names** — `bot/learned-pattern/<skill>-<hash>`.
   Same content produces the same branch. Re-running detect+propose on the
   same cluster is idempotent (no duplicate PRs).
6. **Git worktree** — the PR branch is created in `/tmp/memory-pr-*`, not in
   the user's working directory.

## Clustering Algorithm

- Fetches all cases with `status IN ('active', 'promoted') AND reward >= 0.6`
- L2-normalizes embeddings, computes pairwise cosine distances (scipy pdist)
- Agglomerative linkage with `method='average'` (UPGMA — correct for cosine)
- fcluster with distance threshold **0.15** (tuned for BGE-small compressed distances)
- Filters clusters below `min_cluster_size = max(5, int(0.01 * N))`
- Persists centroids (not cluster IDs) for identity stability across re-runs
- On re-clustering, matches new clusters to existing patterns by centroid
  cosine similarity (threshold 0.10)

## CLI Reference

| Command | Description |
|---|---|
| `memory-proposer detect [--min-cluster N] [--min-reward 0.6]` | Detect clusters and persist as patterns |
| `memory-proposer list [--status detected\|proposed\|merged\|ignored]` | List persisted patterns |
| `memory-proposer propose <id> --target-skill <name>` | Generate draft PR for a pattern |

All commands accept `--json`.

## Setup

```bash
pip install -r ${OPENCODE_PLUGIN_ROOT}/skills/memory-proposer/scripts/requirements.txt
# Requires memory skill to be installed too:
pip install -r ${OPENCODE_PLUGIN_ROOT}/skills/memory/scripts/requirements.txt
```

## Typical Flow

1. Run `memory-proposer detect` periodically (e.g. via `/re:memory-review`)
2. Review detected clusters with `memory-proposer list`
3. For high-quality clusters, run `memory-proposer propose <id> --target-skill <skill>`
4. Review the generated draft PR on GitHub
5. Merge or close — closing also deletes the branch (`gh pr close --delete-branch`)

## Related

- `memory` skill — source of cases the proposer operates on
- `/re:memory-review` command — interactive audit that includes this flow
