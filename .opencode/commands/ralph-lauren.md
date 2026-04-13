---
name: re:ralph-lauren
description: Run frontend design improvement loop — assess, improve, document, repeat
argument-hint: "<url> [--max-iterations N] [--target-score N] [--skip-deterministic]"
---

# Ralph Lauren: Frontend Design Improvement Loop

Run an autonomous evaluate-improve loop on a frontend page using deterministic metrics,
impeccable.style assessment methodology (/audit + /critique), and targeted design improvements.

## Arguments

<args> #$ARGUMENTS </args>

## Execution

### Step 1: Parse Arguments

Parse the arguments from `<args>`. Expected format:
```
<url> [--max-iterations N] [--target-score N] [--skip-deterministic]
```

Defaults:
- `--max-iterations`: 5
- `--target-score`: 85
- `--skip-deterministic`: false

If no URL is provided, use AskUserQuestion:
"What URL should I assess and improve? (e.g., http://localhost:3000)"

### Step 2: Check Dependencies

Run these checks:

```bash
# Required: claude-agent-sdk
python3 -c "import claude_agent_sdk" 2>/dev/null || echo "MISSING: pip install claude-agent-sdk"

# Required: anyio
python3 -c "import anyio" 2>/dev/null || echo "MISSING: pip install anyio"

# Required: agent-browser
command -v agent-browser >/dev/null 2>&1 || echo "MISSING: npm install -g agent-browser"
```

If any required dependency is missing, tell the user what to install and stop.

### Step 2b: Gemini API Key (for segmentation maps)

Check if `GEMINI_API_KEY` is set in the environment:

```bash
[ -n "$GEMINI_API_KEY" ] && echo "GEMINI_API_KEY: set" || echo "GEMINI_API_KEY: not set"
```

If NOT set, use AskUserQuestion:
"Segmentation maps require a Gemini API key. Would you like to provide one? (paste key, or type 'skip' to run without segmentation maps)"

If the user provides a key, pass it via `--gemini-key <key>` to the harness.
If they type "skip", run without segmentation.

### Step 3: Verify Dev Server

Check that the URL is accessible:

```bash
curl -sI <url> | head -1
```

If not accessible, ask the user to start their dev server first.

### Step 4: Run the Harness

Determine the path to the ralph_lauren.py script. It lives relative to this plugin:

```bash
# Find the script
SCRIPT_DIR=$(find ~/.claude/plugins -path "*/ralph-lauren/scripts/ralph_lauren.py" 2>/dev/null | head -1)

# If not found in plugins, check the repo directly
if [ -z "$SCRIPT_DIR" ]; then
  SCRIPT_DIR=$(find . -path "*/ralph-lauren/scripts/ralph_lauren.py" 2>/dev/null | head -1)
fi
```

Run the harness:

```bash
python3 "$SCRIPT_DIR" \
  --url <url> \
  --cwd "$(pwd)" \
  --max-iterations <N> \
  --target-score <N> \
  --gemini-key <KEY_IF_PROVIDED>
```

Omit `--gemini-key` if the user skipped or if `GEMINI_API_KEY` is already in the environment.

The script will output progress to stdout. Let it run — it spawns independent Claude sessions for assessment and improvement.

### Step 5: Review Results

After the harness completes:

1. Read the summary: `docs/ralph-lauren/run-<latest>/summary.md`
2. Read the philosophy: `docs/ralph-lauren/philosophy.md`
3. Present the score progression to the user
4. If the target wasn't reached, suggest running another round

### Step 6: Offer Next Steps

Present options to the user:

1. **Run again** — another round of iterations on the same URL
2. **Run on a different page** — apply the established design system to another route
3. **Review changes** — look at `git diff` to see what was modified
4. **Commit** — commit the design improvements
5. **Done** — stop here
