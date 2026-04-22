#!/usr/bin/env bash
set -euo pipefail

# Transparent stdin filter for stdout from shell tools.
# - Detects JSON and attempts to encode with `toon` for compression.
# - Supports standard JSON and NDJSON (newline-delimited JSON objects).
# - Passes through non-JSON output unchanged.

TOON_BIN="${TOON_BIN:-toon}"
OUTPUT="$(cat)"

if [[ -z "$OUTPUT" ]]; then
  exit 0
fi

FIRST_CHAR="$(printf '%s' "$OUTPUT" | sed -e 's/^[[:space:]]*//' | head -c 1)"
if [[ "$FIRST_CHAR" != "{" && "$FIRST_CHAR" != "[" ]]; then
  printf '%s\n' "$OUTPUT"
  exit 0
fi

if ! command -v "$TOON_BIN" >/dev/null 2>&1; then
  printf '%s\n' "$OUTPUT"
  exit 0
fi

# Try direct JSON object / array encoding first.
ENCODED="$(printf '%s' "$OUTPUT" | "$TOON_BIN" --encode 2>/dev/null || true)"
if [[ -n "$ENCODED" ]]; then
  printf '(original: json; showing: toon)\n%s\n' "$ENCODED"
  exit 0
fi

# Try NDJSON fallback via Node (no jq dependency).
if command -v node >/dev/null 2>&1; then
  ENCODED="$(printf '%s' "$OUTPUT" | node -e '
    const fs = require("fs");
    const data = fs.readFileSync(0, "utf8").trim();
    if (!data) process.exit(1);
    const lines = data.split(/\r?\n/).filter((line) => line.trim().length > 0);
    const parsed = [];
    for (const line of lines) {
      parsed.push(JSON.parse(line));
    }
    process.stdout.write(JSON.stringify(parsed));
  ' 2>/dev/null | "$TOON_BIN" --encode 2>/dev/null || true)"
  if [[ -n "$ENCODED" ]]; then
    printf '(original: ndjson; showing: toon)\n%s\n' "$ENCODED"
    exit 0
  fi
fi

# Last resort: no encoding, pass-through.
printf '%s\n' "$OUTPUT"
