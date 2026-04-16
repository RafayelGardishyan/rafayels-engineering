#!/usr/bin/env bash
# memory-retrieve.sh — PreToolUse hook for the Skill tool.
# Fires before every Skill invocation. If the skill is a workflow phase,
# queries the memory bank and injects retrieved cases as additionalContext.
#
# Requires: a Python 3.10-3.12 with sqlite-vec + fastembed installed. The
# `memory` wrapper picks a capable interpreter automatically.
# Graceful degradation: if memory CLI fails, outputs nothing (hook is a no-op)

set -euo pipefail

# Resolve the latest installed plugin version dynamically
PLUGIN_BASE="$HOME/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering"
PLUGIN_DIR=$(ls -d "$PLUGIN_BASE"/*/ 2>/dev/null | sort -V | tail -1)
if [[ -z "$PLUGIN_DIR" ]]; then
  exit 0  # plugin not installed
fi
MEM="$PLUGIN_DIR/skills/memory/scripts/memory"

if [[ ! -x "$MEM" ]]; then
  exit 0  # memory skill not present in this version
fi

# Read stdin (hook input JSON)
INPUT=$(cat)

# Extract the skill name from tool_input
SKILL=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null)

# Map skill names to memory phases
case "$SKILL" in
  workflows:brainstorm|rafayels-engineering:workflows:brainstorm)
    PHASE="brainstorm" ;;
  workflows:plan|rafayels-engineering:workflows:plan)
    PHASE="plan" ;;
  workflows:work|rafayels-engineering:workflows:work)
    PHASE="work" ;;
  workflows:review|rafayels-engineering:workflows:review)
    PHASE="review" ;;
  workflows:compound|rafayels-engineering:workflows:compound)
    PHASE="compound" ;;
  *)
    exit 0 ;;  # not a workflow skill — skip
esac

# Extract the query text from skill args (the feature description)
QUERY=$(echo "$INPUT" | jq -r '.tool_input.args // empty' 2>/dev/null)
if [[ -z "$QUERY" ]]; then
  exit 0  # no args to query with
fi

# Truncate query to 500 chars to prevent shell issues
QUERY="${QUERY:0:500}"

# Run memory query — capture stdout, suppress stderr
CASES=$("$MEM" query "$QUERY" --phase "$PHASE" --k 3 --format md 2>/dev/null) || true

if [[ -z "$CASES" ]]; then
  exit 0  # no cases retrieved (cold start, deps missing, or empty bank)
fi

# Output JSON with additionalContext to inject the cases into the model's context
jq -n --arg ctx "$CASES" --arg phase "$PHASE" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": ("[Memory Layer] Retrieved relevant cases for " + $phase + " phase:\n\n" + $ctx)
  }
}'
