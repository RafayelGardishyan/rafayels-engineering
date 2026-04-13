---
name: re:update
description: Pull the latest rafayels-engineering plugin and refresh repo-specific skills with current project context. Run after plugin updates or when CLAUDE.md changes.
argument-hint: "[optional: path to the repository, defaults to cwd]"
---

# Update Plugin & Repo Skills

Pull the latest rafayels-engineering plugin from the marketplace and refresh all repo-specific skills with current project details from CLAUDE.md.

## Repository Path

<repo_path> #$ARGUMENTS </repo_path>

## Execution Flow

### Phase 1: Determine Repository

If no path provided, use the current working directory.

```bash
REPO="<repo_path or cwd>"
cd "$REPO" && git rev-parse --is-inside-work-tree
```

Verify `.claude/skills/` exists — if not, suggest running `/re:existing_repo` first.

### Phase 2: Pull Latest Plugin

Update the marketplace repo and sync to the cache:

```bash
cd ~/.claude/plugins/marketplaces/rafayels-marketplace && git pull --ff-only
```

Then sync the marketplace source to the cache directory so new skills are immediately available:

```bash
# Remove stale cache and copy fresh
rm -rf ~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/skills
cp -r ~/.claude/plugins/marketplaces/rafayels-marketplace/plugins/rafayels-engineering/skills \
      ~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/skills
```

Also sync commands and agents:

```bash
rm -rf ~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/commands
cp -r ~/.claude/plugins/marketplaces/rafayels-marketplace/plugins/rafayels-engineering/commands \
      ~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/commands 2>/dev/null || true

rm -rf ~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/agents
cp -r ~/.claude/plugins/marketplaces/rafayels-marketplace/plugins/rafayels-engineering/agents \
      ~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/agents 2>/dev/null || true
```

### Phase 3: Read Current Project Context

Parse the repo's `CLAUDE.md` to extract project details needed for skill customization:

```bash
cat "$REPO/CLAUDE.md"
```

Extract from CLAUDE.md:
- **Project name** — from the `# Project:` heading
- **Language/Framework** — from `Language/Framework:` line
- **Test command** — from `Test command:` line
- **Lint command** — from `Lint command:` line
- **Build command** — from `Build command:` line
- **Docs location** — from `Docs location:` line
- **Dev logs location** — from `Dev logs:` line
- **ADR location** — from `ADRs:` line

If CLAUDE.md doesn't exist or is missing fields, use AskUserQuestion to fill in the gaps.

### Phase 4: Refresh Repo-Specific Skills

For each skill in `$REPO/.claude/skills/`, read the **latest template** from the plugin cache and re-generate it with the project-specific details:

```bash
ls "$REPO/.claude/skills/"
```

For each installed skill directory:

1. Read the **upstream template** from `~/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering/1.0.0/skills/<skill>/SKILL.md`
2. Read the **current repo version** from `$REPO/.claude/skills/<skill>/SKILL.md`
3. Compare: if upstream has new content (sections, tools, instructions), merge it into the repo version while preserving project-specific customizations (paths, commands, project names)
4. Write the updated skill

**Key principle**: Upstream additions (new sections, new tools, new instructions) should be added. Project-specific values (paths, project names, commands) should be preserved from the existing repo skill.

Skills to refresh:
- **check/SKILL.md** — preserve lint command, update structure
- **test/SKILL.md** — preserve test command, update structure
- **fix/SKILL.md** — preserve fix commands, update structure
- **dev-log/SKILL.md** — preserve vault path and project name, update structure
- **using-adr-plugin/SKILL.md** — preserve project name, update tool reference table and new tools (merge, split, list_connections, set_connections, domein field)
- **getting-started/SKILL.md** — preserve setup steps, update structure

For skills that exist upstream but not in the repo, ask:
"New skill `<skill_name>` is available: <skill_description>. Install it?"

### Phase 5: Show Changelog

Show what changed by comparing the upstream skill content:

```
Plugin Update Summary

Plugin version: <version from plugin.json>
Skills updated: <count>

Changes:
  - using-adr-plugin: Added merge, split, connections tools + domein field
  - <skill>: <description of changes>

New skills available:
  - <skill_name>: <description> (installed: yes/no)

Repo skills refreshed:
  - check ✓
  - test ✓
  - fix ✓
  - dev-log ✓
  - using-adr-plugin ✓
  - getting-started ✓
```

### Phase 6: Verify

```bash
# Check all skills are valid
for skill in "$REPO/.claude/skills"/*/SKILL.md; do
  echo "✓ $(dirname $skill | xargs basename)"
done

# Show git diff of changes
cd "$REPO" && git diff --stat .claude/skills/
```

Ask: "Want to commit these skill updates?" If yes:

```bash
git add .claude/skills/
git commit -m "chore: update rafayels-engineering skills to latest upstream"
```

## Error Recovery

- If `git pull` fails (dirty marketplace repo), run `git stash && git pull && git stash pop`
- If a skill template can't be found upstream, keep the existing repo version unchanged
- If CLAUDE.md is missing, prompt user to run `/re:existing_repo` for full setup
