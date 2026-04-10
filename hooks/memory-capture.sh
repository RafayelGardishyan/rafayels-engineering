#!/usr/bin/env bash
# memory-capture.sh — PostToolUse hook for the Skill tool.
# Fires after every successful Skill invocation. If the skill is a workflow phase,
# writes a case to the memory bank with the skill args as the query.
#
# Runs async (non-blocking) so it doesn't slow down workflow transitions.
# Graceful degradation: if memory CLI fails, silently exits.

set -euo pipefail

PY="/opt/homebrew/bin/python3.12"
PLUGIN_BASE="$HOME/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering"
PLUGIN_DIR=$(ls -d "$PLUGIN_BASE"/*/ 2>/dev/null | sort -V | tail -1)
if [[ -z "$PLUGIN_DIR" ]]; then
  exit 0
fi
MEM="$PLUGIN_DIR/skills/memory/scripts/memory.py"

if [[ ! -f "$MEM" ]]; then
  exit 0
fi

INPUT=$(cat)

SKILL=$(echo "$INPUT" | jq -r '.tool_input.skill // empty' 2>/dev/null)

case "$SKILL" in
  workflows:brainstorm|rafayels-engineering:workflows:brainstorm)
    PHASE="brainstorm"; TYPE="decision" ;;
  workflows:plan|rafayels-engineering:workflows:plan)
    PHASE="plan"; TYPE="decision" ;;
  workflows:work|rafayels-engineering:workflows:work)
    PHASE="work"; TYPE="solution" ;;
  workflows:review|rafayels-engineering:workflows:review)
    PHASE="review"; TYPE="pattern" ;;
  workflows:compound|rafayels-engineering:workflows:compound)
    PHASE="compound"; TYPE="solution" ;;
  *)
    exit 0 ;;
esac

QUERY=$(echo "$INPUT" | jq -r '.tool_input.args // empty' 2>/dev/null)
if [[ -z "$QUERY" ]]; then
  exit 0
fi

QUERY="${QUERY:0:500}"
TITLE="${PHASE} phase: ${QUERY:0:150}"

# Write the case — capture case_id for future signal emission
RESULT=$("$PY" "$MEM" --json write \
  --phase "$PHASE" \
  --type "$TYPE" \
  --title "$TITLE" \
  --query "$QUERY" \
  --tags "[\"$PHASE\",\"auto-captured\"]" \
  2>/dev/null) || true

if [[ -n "$RESULT" ]]; then
  CASE_ID=$(echo "$RESULT" | jq -r '.case_id // empty' 2>/dev/null)
  if [[ -n "$CASE_ID" ]]; then
    # Emit an approval signal — the workflow completed successfully
    "$PY" "$MEM" signal "$CASE_ID" approval 1.0 --source "hook:post-skill" 2>/dev/null || true
  fi
fi

exit 0
