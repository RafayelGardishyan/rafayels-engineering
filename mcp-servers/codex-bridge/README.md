# Codex Bridge MCP Server

A lightweight stdio MCP server that delegates coding tasks to the OpenAI Codex CLI, enabling Claude Code and Codex to communicate and collaborate.

## Tools

- `delegate_coding_task` — Send a coding task to Codex and receive structured results
- `codex_review_code` — Ask Codex to review code or files
- `codex_answer_question` — Ask Codex a technical, non-mutating question
- `get_codex_version` — Check the installed Codex CLI version

## Usage

Registered automatically via `.claude-plugin/plugin.json` when the plugin is loaded.

## Requirements

- `codex` CLI installed and authenticated
- Python 3.10+
- `mcp` Python SDK (`pip install mcp`)


