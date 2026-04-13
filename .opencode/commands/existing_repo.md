---
name: re:existing_repo
description: Configure the rafayels-engineering plugin for an existing repository — sets up documentation paths, project details, and installs skills with repo-specific context baked in.
argument-hint: "[optional: path to the repository]"
---

# Set Up Existing Repository

Configure the rafayels-engineering plugin for an existing project by gathering project-specific details and installing skills with baked-in context.

## Repository Path

<repo_path> #$ARGUMENTS </repo_path>

## Execution Flow

### Phase 1: Identify the Repository

**If no path provided**, use AskUserQuestion:
"What's the path to your existing repository? (e.g., `/Users/you/projects/my-app`)"

Verify the path exists and is a git repository:
```bash
cd <repo_path> && git rev-parse --is-inside-work-tree
```

If not a git repo, ask: "This directory isn't a git repository. Would you like to initialize one, or provide a different path?"

### Phase 2: Gather Project Information

Use AskUserQuestion to collect the following details **one at a time**:

1. **Project name**: "What's the name of this project?" (suggest based on directory name)

2. **Project description**: "Give a brief description of what this project does."

3. **Documentation location**: "Where is your project documentation stored?"
   - Options:
     a. `docs/` directory in the repo (default)
     b. External Obsidian vault (provide path)
     c. Wiki or other location (provide details)
     d. No documentation yet (we'll set it up)

4. **Dev log location**: "Where should dev logs be stored?"
   - Options:
     a. `docs/dev-logs/` in the repo
     b. Obsidian vault path (e.g., `/Users/you/Documents/vault/Project/Dev Log/`)
     c. Other location

5. **ADR storage**: "Where should Architecture Decision Records be stored?"
   - Options:
     a. Use the obsidian-adr MCP plugin (recommended — provide Obsidian vault path and project name)
     b. `docs/adr/` in the repo
     c. Other location

6. **Language/framework**: "What's the primary language and framework?" (auto-detect from repo if possible)
   ```bash
   # Auto-detect
   ls <repo_path>/Gemfile <repo_path>/package.json <repo_path>/go.mod <repo_path>/Cargo.toml <repo_path>/requirements.txt <repo_path>/pyproject.toml 2>/dev/null
   ```

7. **Test command**: "What command runs your test suite?" (e.g., `make test`, `npm test`, `go test ./...`)

8. **Lint command**: "What command runs your linter?" (e.g., `make lint`, `npm run lint`)

9. **Build command**: "What command builds the project?" (e.g., `make build`, `npm run build`, or "N/A")

10. **Project tracker**: "What project tracker do you use?"
    - Options: GitHub Issues, Linear, None

### Phase 3: Install Plugin Skills

Create the `.claude/` directory structure in the target repo with project-specific details baked into each skill.

```bash
mkdir -p <repo_path>/.claude/skills/check
mkdir -p <repo_path>/.claude/skills/test
mkdir -p <repo_path>/.claude/skills/fix
mkdir -p <repo_path>/.claude/skills/dev-log
mkdir -p <repo_path>/.claude/skills/using-adr-plugin
mkdir -p <repo_path>/.claude/skills/getting-started
mkdir -p <repo_path>/docs/brainstorms
mkdir -p <repo_path>/docs/plans
mkdir -p <repo_path>/docs/solutions
```

#### 3.1 Generate `CLAUDE.md`

Create or update `<repo_path>/CLAUDE.md` with project-specific configuration:

```markdown
# Project: <project_name>

<project_description>

## Development

- **Language/Framework**: <language_framework>
- **Test command**: `<test_command>`
- **Lint command**: `<lint_command>`
- **Build command**: `<build_command>`
- **Project tracker**: <tracker>

## Documentation

- **Docs location**: <docs_location>
- **Dev logs**: <dev_log_location>
- **ADRs**: <adr_location>

## Conventions

- Follow existing code patterns
- Write tests for new functionality
- Update documentation when changing behavior
- Create ADRs for architectural decisions
- Write dev log entries after merging PRs
```

#### 3.2 Install Skills with Baked-In Paths

For each skill, customize the template with the gathered project details:

**dev-log/SKILL.md**: Replace vault path and project name with the user's answers.

**using-adr-plugin/SKILL.md**: Replace project name with user's project in all MCP tool calls.

**check/SKILL.md**: Replace `make check` with the user's lint command.

**test/SKILL.md**: Replace `make test-all` with the user's test command.

**fix/SKILL.md**: Customize auto-fix commands for the user's language/framework.

**getting-started/SKILL.md**: Customize setup steps for the user's project.

### Phase 4: Install Plugin Reference

Add the rafayels-engineering plugin to the project's Claude settings so `/re:feature` and other commands are available:

Check if `.claude/settings.json` exists and add the plugin:

```bash
# Check for existing settings
cat <repo_path>/.claude/settings.json 2>/dev/null || echo '{}'
```

Ensure the rafayels-engineering plugin path is referenced. If using a global plugin installation, the user may need to add it via:
```bash
claude plugin add <path-to-rafayels-engineering>
```

### Phase 5: Verify Setup

Run a quick verification:

```bash
cd <repo_path>

# Check .claude directory
ls -la .claude/skills/

# Check docs directories
ls -la docs/brainstorms/ docs/plans/ docs/solutions/ 2>/dev/null

# Check CLAUDE.md
cat CLAUDE.md

# Verify git status
git status
```

### Phase 6: Summary

Present the setup results:

```
Repository configured!

Project: <project_name>
Path: <repo_path>

Installed skills:
  - /check — runs <lint_command>
  - /test — runs <test_command>
  - /fix — auto-fix lint issues
  - /dev-log — create dev log entries at <dev_log_location>
  - /using-adr-plugin — manage ADRs at <adr_location>
  - /getting-started — project setup guide

Created directories:
  - docs/brainstorms/
  - docs/plans/
  - docs/solutions/

Configuration:
  - CLAUDE.md — project conventions and settings

Available commands:
  - /re:feature — full feature pipeline
  - /workflows:brainstorm — explore ideas
  - /workflows:plan — create implementation plans
  - /workflows:work — execute plans
  - /workflows:review — code review
  - /workflows:compound — document solutions

Next steps:
  1. Review CLAUDE.md and adjust conventions
  2. Run /re:feature to start your first feature!
```
