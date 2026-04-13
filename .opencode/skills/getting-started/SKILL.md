---
name: getting-started
description: Set up a fresh clone for development. Run when node_modules/ is missing, git hooks are not configured, or after first clone.
---

# Getting Started

## Quick Start

Run all setup commands from the project root.

## Instructions

### 1. Install Go tools

```bash
go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@latest
go install github.com/air-verse/air@latest
```

### 2. Install frontend dependencies

```bash
cd frontend && bun install
cd modules/chat/frontend && bun install
cd email && bun install
cd e2e && bun install
```

### 3. Build prerequisites

```bash
make build-modules
make build-emails
```

### 4. Configure git hooks and verify

```bash
make dev-setup
make check
```

### 5. Start development

```bash
make docker-up   # Start SurrealDB
make dev          # Start file watchers (Air + chokidar + Vite)
```

## Verification

After setup, `make check` must pass with 0 errors. If it fails:

- Missing golangci-lint: re-run step 1
- Missing bun dependencies: re-run step 2
- Missing build artifacts: re-run step 3
- Git hooks not configured: run `make dev-setup`

## On Failure

If `make check` still fails after all steps, run `/fix` to auto-fix lint issues, then re-run `make check`.
