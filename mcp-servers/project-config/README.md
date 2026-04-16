# Project Config MCP Server

A lightweight stdio MCP server that exposes the layered `.rafayels/config.yaml` resolver so agents can read project configuration (vault path, ADR project, dev-log subpath, memory DB path, docs dirs) without shelling out.

## Tools

- `get_config_value(key)` — Return one resolved config value
- `get_all_config()` — Return every resolved key with value and source
- `get_config_source(key)` — Return which layer (team/local/env/default) supplied a key
- `list_config_keys()` — Return the full schema (keys, types, defaults)
- `get_project_root()` — Return the discovered project root
- `check_config()` — Validate config without raising (doctor diagnostics)
- `init_config(values, force=False)` — Non-interactive bootstrap of `.rafayels/config.yaml`

All tools return dicts with a `status` key (`"ok"` or `"error"`). Errors include `error_type`, `message`, and an optional `fix` hint.

## Usage

Registered automatically via `.claude-plugin/plugin.json` when the plugin is loaded.

## Requirements

- Python 3.10+
- `mcp>=1.26,<2.0`
- `pyyaml>=6.0`

Install: `pip install -r requirements.txt`
