---
name: fix
description: Auto-fix lint and formatting issues in Go and frontend code. Use when /check reports fixable violations or after writing new code.
---

# Auto-Fix Lint Issues

## Quick Start

```bash
# Go
golangci-lint run --fix . ./data/... ./llm/... ./modules/... ./auth/... ./email/...

# Frontend
cd frontend && bun run lint:fix
cd modules/chat/frontend && bun run lint:fix
```

## Instructions

1. Run the auto-fix commands above
2. Run `make check` to verify all issues are resolved
3. If issues remain, they require manual fixes — read the error output

## What Gets Fixed Automatically

- **Go**: formatting (gofmt/goimports), simple patterns (gocritic suggestions)
- **Frontend**: formatting (indentation, quotes, semicolons), import ordering, unused imports
