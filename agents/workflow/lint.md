---
name: lint
description: "Runs linting and code quality checks on Go and TypeScript files. Use before pushing to origin."
model: inherit
---

Your workflow process:

1. **Initial Assessment**: Determine which checks are needed based on the files changed or the specific request
2. **Execute Appropriate Tools**:
   - For Go files: `golangci-lint run ./...` for checking, `golangci-lint run --fix ./...` for auto-fixing
   - For TypeScript/Svelte files: `npm run lint` or `bun run lint` for checking, `npm run lint:fix` or `bun run lint:fix` for auto-fixing
   - For type checking: `npm run check` or `svelte-check` for SvelteKit projects
   - For security: `gosec ./...` for Go vulnerability scanning
3. **Analyze Results**: Parse tool outputs to identify patterns and prioritize issues
4. **Take Action**: Commit fixes with `style: linting`
