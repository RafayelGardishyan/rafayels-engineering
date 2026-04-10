# YAML Frontmatter Schema

Track-based schema: learnings are classified as either **bug track** or **knowledge track**.
Different tracks require different fields — bugs need root causes and fixes, knowledge needs context and guidance.

## File Organization

**Flat structure with prefix IDs** (not category folders):

```
docs/solutions/
  BUG-0001-missing-null-check.md
  BUG-0002-redis-connection-pool.md
  KNW-0001-structured-logging.md
  KNW-0002-error-boundary-pattern.md
  _index.md                          # Auto-generated table
  patterns/
    critical-patterns.md             # Cross-cutting patterns
```

Flat structure avoids taxonomy debates and enables cross-cutting discovery via `scope` tags.

## Bug Track

For documented bugs, build errors, test failures, and runtime errors.

```yaml
---
id: BUG-0001                          # Prefix-based ID
title: "Missing null check in user service"
type: bug
problem_type: runtime_error           # build_error | test_failure | runtime_error | performance_issue | database_issue | security_issue
severity: high                        # critical | high | medium | low
frequency: recurring                  # one-off | recurring | systemic
symptoms:
  - "TypeError: Cannot read property 'id' of null"
  - "500 error on /api/users/:id endpoint"
root_cause: "Missing guard clause before accessing user.organization"
resolution_type: code_fix             # code_fix | config_change | dependency_update | workaround
environment: [ci, production]         # where it manifests
scope: [typescript, user-service]     # searchable tags
related: [BUG-0003]                   # cross-references
supersedes: []                        # replaces older learnings
last_validated: 2026-04-10            # prevents staleness
---
```

### Required Fields (Bug Track)
- `id`, `title`, `type: bug`, `problem_type`, `severity`, `symptoms`, `root_cause`, `resolution_type`, `scope`, `last_validated`

## Knowledge Track

For best practices, documentation gaps, and workflow improvements.

```yaml
---
id: KNW-0001
title: "Prefer structured logging over string interpolation"
type: knowledge
problem_type: best_practice           # best_practice | documentation_gap | workflow_issue
confidence: established               # experimental | established | deprecated
applies_when: "Adding logging to any Go or TypeScript service"
guidance: "Use slog (Go) or pino (TS) with structured fields, not fmt.Sprintf or template literals"
scope: [go, typescript, logging]
related: []
supersedes: []
last_validated: 2026-04-10
---
```

### Required Fields (Knowledge Track)
- `id`, `title`, `type: knowledge`, `problem_type`, `confidence`, `applies_when`, `guidance`, `scope`, `last_validated`

## Field Details

### `supersedes` — Aggressive Merging
When 5 learnings document the same flaky test issue, merge them into one canonical doc and list the replaced IDs here. This prevents a graveyard of redundant learnings.

### `last_validated` — Staleness Prevention
The `learnings-researcher` agent flags learnings with `last_validated` > 6 months old as potentially stale. Re-validate or archive them.

### `scope` — Searchable Tags
Lowercase, hyphen-separated keywords. Used for grep filtering:
```bash
grep -l "scope:.*typescript" docs/solutions/*.md
```

## Quality Guidelines

- Keep body under 150 words (long docs don't get read)
- Include exact error messages for bug-track entries
- Include concrete code examples in knowledge-track entries
- Surface at point-of-need: the `symptoms` field is grepped against current errors

## Validation Rules

1. All required fields for the chosen track must be present
2. `id` must match pattern `^(BUG|KNW)-\d{4}$`
3. `type` must be `bug` or `knowledge`
4. Enum fields must match allowed values exactly
5. `symptoms` must be YAML array with 1-5 items (bug track only)
6. `last_validated` must match YYYY-MM-DD format
