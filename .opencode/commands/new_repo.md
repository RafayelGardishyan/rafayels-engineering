---
name: re:new_repo
description: Create a new repository from scratch with the rafayels-engineering plugin installed, documentation structure, and project-specific skills baked in.
argument-hint: "[optional: project name]"
---

# Create New Repository

Create a new git repository with the full rafayels-engineering toolkit installed from the start — documentation structure, skills, CLAUDE.md, and the compound engineering plugin.

## Project Name

<project_name_arg> #$ARGUMENTS </project_name_arg>

## Execution Flow

### Phase 1: Gather Project Information

Use AskUserQuestion to collect details **one at a time**:

1. **Project name**: "What's the name of your new project?"
   - If provided via arguments, confirm: "Creating project '<name>'. Correct?"
   - Suggest kebab-case for the directory name

2. **Project location**: "Where should the project be created?"
   - Default: current working directory
   - Example: `/Users/you/Documents/projects/`

3. **Project description**: "Give a brief description of what this project will do."

4. **Language/framework**: "What language and framework will you use?"
   - Options with smart defaults:
     a. Ruby on Rails
     b. Go
     c. Node.js / TypeScript
     d. Python
     e. Rust
     f. Other (specify)

5. **Documentation location**: "Where should documentation live?"
   - Options:
     a. `docs/` directory in the repo (default)
     b. External Obsidian vault (provide path)

6. **Dev log location**: "Where should dev logs be stored?"
   - Options:
     a. `docs/dev-logs/` in the repo (default)
     b. Obsidian vault path

7. **ADR storage**: "Where should Architecture Decision Records be stored?"
   - Options:
     a. Use the obsidian-adr MCP plugin (provide Obsidian vault path and project name)
     b. `docs/adr/` in the repo (default)

8. **Git remote**: "Do you want to create a GitHub repository?"
   - Options:
     a. Yes, public
     b. Yes, private (default)
     c. No, local only for now

9. **Project tracker**: "What project tracker will you use?"
   - Options: GitHub Issues (default), Linear, None

### Phase 2: Create Repository

```bash
# Create project directory
mkdir -p <location>/<project-name>
cd <location>/<project-name>

# Initialize git
git init
```

### Phase 3: Create Project Structure

Generate the full project structure based on language/framework choice.

#### 3.1 Common Structure (all projects)

```bash
# Documentation
mkdir -p docs/brainstorms
mkdir -p docs/plans
mkdir -p docs/solutions

# Claude skills
mkdir -p .claude/skills/check
mkdir -p .claude/skills/test
mkdir -p .claude/skills/fix
mkdir -p .claude/skills/dev-log
mkdir -p .claude/skills/using-adr-plugin
mkdir -p .claude/skills/getting-started
```

#### 3.2 Language-Specific Scaffolding

**Ruby on Rails**:
```bash
# If rails is available, use it; otherwise create basic structure
rails new . --skip-git 2>/dev/null || mkdir -p app lib config db spec
```

**Go**:
```bash
go mod init <module-name>
mkdir -p cmd internal pkg
```

**Node.js / TypeScript**:
```bash
npm init -y
mkdir -p src tests
# If TypeScript, add tsconfig.json
```

**Python**:
```bash
mkdir -p src tests
touch src/__init__.py
# Create pyproject.toml or setup.py
```

**Rust**:
```bash
cargo init .
```

### Phase 4: Generate Configuration Files

#### 4.1 CLAUDE.md

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

## Getting Started

Run `/getting-started` to set up your development environment.
```

#### 4.2 .gitignore

Generate appropriate `.gitignore` for the chosen language/framework.

```bash
# Fetch from gitignore.io or use a sensible default
curl -sL "https://www.toptal.com/developers/gitignore/api/<language>" > .gitignore 2>/dev/null
```

Add common Claude/IDE entries:
```
# Claude Code
.claude/settings.local.json
```

#### 4.3 README.md

```markdown
# <project_name>

<project_description>

## Getting Started

[Setup instructions based on language/framework]

## Development

- Run tests: `<test_command>`
- Run linter: `<lint_command>`

## Documentation

- [Brainstorms](docs/brainstorms/) — Feature exploration
- [Plans](docs/plans/) — Implementation plans
- [Solutions](docs/solutions/) — Documented problem solutions
```

### Phase 5: Install Skills with Baked-In Context

Generate each skill file customized for this project:

**dev-log/SKILL.md**: Configure with the chosen dev log location, project name.

**using-adr-plugin/SKILL.md**: Configure with the chosen ADR storage, project name for MCP calls.

**check/SKILL.md**: Configure with the language-appropriate lint command.

**test/SKILL.md**: Configure with the language-appropriate test command.

**fix/SKILL.md**: Configure with language-appropriate auto-fix commands.

**getting-started/SKILL.md**: Configure with language-specific setup steps.

### Phase 6: Install Compound Engineering Plugin

Ensure the compound engineering plugin is available:

```bash
# Check if already installed
claude plugin list 2>/dev/null | grep compound

# If not installed, install it
claude plugin add compound-engineering 2>/dev/null
```

Also ensure the rafayels-engineering plugin is referenced:
```bash
claude plugin add <path-to-rafayels-engineering> 2>/dev/null
```

### Phase 7: Create GitHub Repository (if requested)

```bash
# Create GitHub repo
gh repo create <project-name> --<public|private> --source=. --push

# Or just set up remote
git remote add origin <url>
```

### Phase 8: Initial Commit

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat: initial project setup with rafayels-engineering toolkit

- Project structure for <language/framework>
- Documentation directories (brainstorms, plans, solutions)
- Claude skills (check, test, fix, dev-log, adr, getting-started)
- CLAUDE.md with project conventions
- README.md

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Phase 9: Create Initial ADR (if using ADR plugin)

If the user chose the obsidian-adr MCP plugin, create the first ADR:

```bash
skill: using-adr-plugin
```

Create ADR-001: "Project Initialization and Technology Choices"
- Record the language/framework choice and rationale
- Record documentation strategy
- Link to any relevant existing ADRs in other projects

### Phase 10: Summary

```
New repository created!

Project: <project_name>
Path: <location>/<project-name>
GitHub: <repo-url> (if created)

Structure:
  <project-name>/
  |- .claude/skills/     (6 skills installed)
  |- docs/
  |  |- brainstorms/
  |  |- plans/
  |  |- solutions/
  |- src/ (or app/, cmd/, etc.)
  |- CLAUDE.md
  |- README.md
  |- .gitignore

Installed skills:
  - /check, /test, /fix — quality gates
  - /dev-log — development logging
  - /using-adr-plugin — architecture decisions
  - /getting-started — setup guide

Available commands:
  - /re:feature — full feature pipeline
  - /workflows:brainstorm, /workflows:plan, /workflows:work
  - /workflows:review, /workflows:compound

Next steps:
  1. Review CLAUDE.md and adjust to your preferences
  2. Run /re:feature to start your first feature!
  3. Or run /getting-started to set up the dev environment
```

## Error Recovery

- If `gh repo create` fails, continue without remote and inform user
- If language scaffolding fails (e.g., `rails new`), create minimal structure manually
- If plugin installation fails, provide manual installation instructions
