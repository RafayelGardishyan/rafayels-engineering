---
name: github
description: Manage GitHub repositories, issues, pull requests, releases, actions, and more using the gh CLI. Use when creating repos, managing issues/PRs, checking CI status, creating releases, or any GitHub operations.
---

# GitHub CLI (`gh`) Skill

## Overview

Use the `gh` CLI for all GitHub operations. This skill covers repos, issues, pull requests, releases, actions, and repository settings.

## Prerequisites

```bash
# Check gh is installed and authenticated
gh auth status
```

If not authenticated: `gh auth login`

## Common Operations

### Repository Management

```bash
# Create a new repo
gh repo create <name> --private --source=. --push
gh repo create <name> --public --source=. --push

# Clone a repo
gh repo clone <owner>/<repo>

# View repo info
gh repo view <owner>/<repo>

# Fork a repo
gh repo fork <owner>/<repo> --clone

# Set default repo (useful in worktrees)
gh repo set-default <owner>/<repo>

# Archive a repo
gh repo archive <owner>/<repo>

# Delete a repo (destructive — confirm with user first)
gh repo delete <owner>/<repo> --yes

# List your repos
gh repo list --limit 20
gh repo list --language go
```

### Pull Requests

```bash
# Create a PR
gh pr create --title "feat: description" --body "## Summary\n- Change 1\n- Change 2"

# Create PR with body from file
gh pr create --title "feat: description" --body-file docs/plans/plan.md

# Create draft PR
gh pr create --title "wip: description" --draft

# List PRs
gh pr list
gh pr list --state open --author @me

# View PR details
gh pr view <number>
gh pr view <number> --json title,body,files,reviews,comments

# Check out a PR locally
gh pr checkout <number>

# View PR diff
gh pr diff <number>

# Review a PR
gh pr review <number> --approve
gh pr review <number> --request-changes --body "Reason"
gh pr review <number> --comment --body "Comment"

# Merge a PR
gh pr merge <number> --squash --delete-branch
gh pr merge <number> --merge
gh pr merge <number> --rebase

# Enable automerge
gh pr merge <number> --auto --squash

# Close a PR
gh pr close <number>

# View PR checks/CI status
gh pr checks <number>
gh pr checks <number> --watch

# Add labels
gh pr edit <number> --add-label "bug,priority:high"

# Add reviewers
gh pr edit <number> --add-reviewer username1,username2

# View PR comments
gh api repos/<owner>/<repo>/pulls/<number>/comments
```

### Issues

```bash
# Create an issue
gh issue create --title "Bug: description" --body "Steps to reproduce..."

# Create issue with labels
gh issue create --title "feat: description" --label "enhancement" --body-file docs/plans/plan.md

# List issues
gh issue list
gh issue list --state open --label "bug"
gh issue list --assignee @me

# View an issue
gh issue view <number>

# Close an issue
gh issue close <number> --reason completed

# Reopen an issue
gh issue reopen <number>

# Edit an issue
gh issue edit <number> --title "New title"
gh issue edit <number> --add-label "priority:high"
gh issue edit <number> --add-assignee @me

# Pin an issue
gh issue pin <number>

# Transfer an issue
gh issue transfer <number> <destination-repo>

# Search issues
gh issue list --search "keyword in:title,body"
```

### GitHub Actions / CI

```bash
# List workflow runs
gh run list
gh run list --workflow=ci.yml

# View a specific run
gh run view <run-id>

# Watch a run in progress
gh run watch <run-id>

# View run logs
gh run view <run-id> --log
gh run view <run-id> --log-failed

# Re-run a failed workflow
gh run rerun <run-id>
gh run rerun <run-id> --failed

# Trigger a workflow manually
gh workflow run <workflow-name>
gh workflow run <workflow-name> --ref <branch>

# List workflows
gh workflow list

# Disable/enable a workflow
gh workflow disable <workflow-name>
gh workflow enable <workflow-name>
```

### Releases

```bash
# Create a release
gh release create v1.0.0 --title "v1.0.0" --notes "Release notes here"

# Create release with auto-generated notes
gh release create v1.0.0 --generate-notes

# Create draft release
gh release create v1.0.0 --draft --generate-notes

# Upload assets to a release
gh release upload v1.0.0 ./dist/binary-linux ./dist/binary-darwin

# List releases
gh release list

# View a release
gh release view v1.0.0

# Delete a release
gh release delete v1.0.0
```

### Labels

```bash
# Create a label
gh label create "priority:high" --color FF0000 --description "High priority"

# List labels
gh label list

# Edit a label
gh label edit "bug" --color 00FF00

# Delete a label
gh label delete "old-label"
```

### GitHub API (for anything not covered by built-in commands)

```bash
# GET request
gh api repos/<owner>/<repo>

# POST request
gh api repos/<owner>/<repo>/issues --method POST --field title="Title" --field body="Body"

# GraphQL query
gh api graphql -f query='{ viewer { login } }'

# Paginated results
gh api repos/<owner>/<repo>/issues --paginate

# With jq filtering
gh api repos/<owner>/<repo>/pulls --jq '.[].title'
```

### Repository Settings

```bash
# Set branch protection (via API)
gh api repos/<owner>/<repo>/branches/main/protection \
  --method PUT \
  --input - <<EOF
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "restrictions": null
}
EOF

# Enable auto-merge on repo
gh api repos/<owner>/<repo> --method PATCH --field allow_auto_merge=true

# Set default branch
gh api repos/<owner>/<repo> --method PATCH --field default_branch=main

# Add secrets for actions
gh secret set SECRET_NAME --body "secret-value"
gh secret list

# Add deploy keys
gh repo deploy-key add key.pub --title "CI Deploy Key"
```

## Workflow Patterns

### Feature Branch → PR → Merge

```bash
# 1. Create and push branch
git checkout -b feat/my-feature
# ... make changes, commit ...
git push -u origin feat/my-feature

# 2. Create PR
gh pr create --title "feat: my feature" --body "Description"

# 3. Wait for CI
gh pr checks <number> --watch

# 4. Merge when ready
gh pr merge <number> --squash --delete-branch
```

### Quick Issue → Branch → PR

```bash
# 1. Create issue
gh issue create --title "feat: add user profiles" --label "enhancement"

# 2. Create branch from issue
git checkout -b feat/add-user-profiles
# ... implement ...
git push -u origin feat/add-user-profiles

# 3. Create PR linking the issue
gh pr create --title "feat: add user profiles" --body "Closes #<issue-number>"
```

### Release Flow

```bash
# 1. Create release branch
git checkout -b release/v1.0.0
git push -u origin release/v1.0.0

# 2. Create PR for release
gh pr create --title "Release v1.0.0" --base main

# 3. After merge, tag and release
gh release create v1.0.0 --generate-notes --target main
```

## Tips

- Use `--json` flag with `--jq` for machine-readable output
- Use `--web` flag to open any resource in the browser: `gh pr view <number> --web`
- Set `GH_REPO` env var to avoid specifying owner/repo in every command
- Use `gh alias set` to create shortcuts for common operations
- PR descriptions support markdown — use `--body-file` for complex descriptions

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Force pushing without checking PR status | Always `gh pr checks` before force push |
| Creating PR from main branch | Create a feature branch first |
| Forgetting to link issues | Use "Closes #N" or "Fixes #N" in PR body |
| Not checking CI before merge | Use `gh pr checks --watch` |
| Deleting branches with open PRs | Close or merge PRs first |
