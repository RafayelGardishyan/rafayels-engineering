---
name: check
description: Run all quality checks (Go lint, frontend lint, typecheck). Use before committing, creating PRs, or when you need to verify code quality passes.
---

# Quality Check

## Quick Start

```bash
make check
```

## Instructions

`make check` runs three checks sequentially. All must pass.

**Note:** This does NOT run tests. Use `make test` or `/test` separately.

1. **Go lint** — `golangci-lint` with depguard architecture rules, errcheck, gosec, complexity limits
2. **Frontend lint** — Biome check on `frontend/` and `modules/chat/frontend/`
3. **Typecheck** — `svelte-check` on both frontend projects

Run individual checks when debugging:

```bash
make lint            # Go only
make lint-frontend   # Biome only
make typecheck       # svelte-check only
```

## On Failure

- Read the error output carefully
- Use `/fix` for auto-fixable lint and formatting issues
- Fix remaining issues manually
- Re-run `make check` to confirm

All checks must pass before committing or creating a PR.
