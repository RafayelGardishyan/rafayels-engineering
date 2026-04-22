# Installation

Use the installer to choose which agent and project should receive the toolkit:

```bash
./install.sh
```

## Supported targets

- **Pi**
  - global install for all projects
  - project-local install for a specific project
- **Claude Code**
  - keeps using `.claude-plugin/plugin.json` and existing MCP setup
- **OpenCode**
  - keeps using `.opencode/`

## Pi-specific additions

This repository is also a valid Pi package via `package.json`:

```bash
pi install /path/to/rafayels-engineering
pi install -l /path/to/rafayels-engineering
```

Pi-native extensions added in `extensions/`:

- `extensions/memory.ts`
- `extensions/project-config.ts`
- `extensions/playwright.ts`
- `extensions/figma.ts`

## Memory setup

After installation, initialize memory once:

```bash
python3 skills/memory/scripts/memory.py init
```

If your environment needs a specific Python, set:

```bash
export PYTHON_FOR_RAFAYELS_ENGINEERING=/opt/homebrew/bin/python3.12
```
