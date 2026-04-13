---
name: test
description: Run all tests (Go unit tests + frontend tests). Use after implementing features, fixing bugs, or before creating PRs to verify correctness.
---

# Run Tests

## Quick Start

```bash
make test-all
```

## Instructions

`make test-all` runs both Go and frontend test suites:

1. **Go tests** — `go test -race -count=1` across all packages (excludes `example/`)
2. **Frontend tests** — Vitest for both `frontend/` and `modules/chat/frontend/`

Run individual suites when debugging:

```bash
make test            # Go only
make test-frontend   # Frontend only (Vitest)
make test-e2e        # Playwright E2E (requires make docker-up + seed)
```

## Prerequisites

Tests require built embed prerequisites (chat frontend bundle + email templates):

```bash
make build-modules   # Build chat frontend bundle
make build-emails    # Compile MJML templates
```

On a fresh clone, run `/getting-started` first — it handles all prerequisites.

## On Failure

- Read the error output carefully
- Go test failures show the file, line, and assertion that failed
- Frontend test failures show the component and test case
- Fix the issue and re-run the specific test suite
- **All tests must pass before claiming work is done**

## Note

This runs unit tests only. For quality checks (lint, typecheck), use `/check`.
For E2E tests, use `make test-e2e` (requires Docker + SurrealDB).
