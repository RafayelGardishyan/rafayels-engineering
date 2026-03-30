---
date: 2026-03-30
topic: ralph-lauren-harness
brainstorm: docs/brainstorms/2026-03-30-ralph-lauren-brainstorm.md
---

# Implementation Plan: Ralph Lauren Frontend Design Loop

## Overview

Python harness using Claude Agent SDK that runs an autonomous evaluate-improve loop on frontend pages. Three components: deterministic metrics (Lighthouse/axe/CSS), subjective assessment (Claude session with impeccable.style rubric + agent-browser), and improver (Claude session with full edit tools). A persistent `philosophy.md` acts as the evolving page-agnostic design system.

## File Structure

```
skills/ralph-lauren/
├── SKILL.md
├── scripts/
│   ├── ralph_lauren.py      # Main orchestrator (CLI entry point)
│   ├── assessor.py           # Subjective assessment via Claude Agent SDK
│   ├── improver.py           # Design improvement via Claude Agent SDK
│   └── metrics.py            # Deterministic metric collection
└── references/
    └── assessment-rubric.md  # Scoring rubric (injected as system prompt context)

commands/re/
└── ralph-lauren.md           # Claude Code command
```

## Step 1: Assessment Rubric (`references/assessment-rubric.md`)

The rubric the subjective assessor uses. Inspired by impeccable.style's `/audit` and `/critique` commands.

**Scoring dimensions (each 0-100):**

| Dimension | What it measures | Key criteria |
|-----------|-----------------|--------------|
| Heuristics | Nielsen's 10 usability heuristics | Visibility of system status, match between system and real world, user control, consistency, error prevention, recognition over recall, flexibility, aesthetic minimalism, error recovery, help/documentation |
| Typography | Type quality | Scale consistency, hierarchy clarity, line length, line height, font pairing, weight usage |
| Layout | Spatial organization | Grid consistency, spacing rhythm, alignment, whitespace usage, responsive behavior |
| Color | Color system | Palette coherence, contrast ratios (WCAG), harmony, semantic meaning, dark/light consistency |
| Craft | Polish & detail | Micro-interactions, border radii consistency, shadow system, icon consistency, loading states |
| Originality | Distinctiveness | Avoids generic AI/template aesthetics, has personality, custom decisions over defaults |

**Overall score** = weighted average: Heuristics(20%) + Typography(15%) + Layout(20%) + Color(15%) + Craft(15%) + Originality(15%)

**Output format**: Structured JSON with per-dimension score, findings (specific issues with severity P0-P3), and actionable recommendations.

## Step 2: Deterministic Metrics (`scripts/metrics.py`)

Pure Python module. No Claude involved. Runs subprocess commands and parses output.

```python
async def collect_metrics(url: str) -> dict:
    """Collect deterministic metrics for a URL."""
    lighthouse = await run_lighthouse(url)   # npx lighthouse --output=json
    axe_results = await run_axe(url)         # npx axe <url> --stdout
    css_stats = await analyze_css(url)       # Parse CSS from page source
    return {
        "lighthouse": lighthouse,  # performance, a11y, best-practices, seo scores
        "accessibility": axe_results,  # violations, passes, incomplete
        "css": css_stats,  # selector count, color count, font families, specificity
    }
```

**Functions:**
- `run_lighthouse(url)` → subprocess `npx lighthouse <url> --output=json --chrome-flags="--headless --no-sandbox"` → parse JSON for category scores
- `run_axe(url)` → subprocess `npx axe <url> --stdout` → parse for violations count + details
- `analyze_css(url)` → fetch page, extract `<style>` and linked CSS, count: selectors, unique colors, font families, max specificity, `!important` count

**Fallback**: If lighthouse/axe not installed, skip gracefully with a warning and null scores.

## Step 3: Subjective Assessor (`scripts/assessor.py`)

Claude Agent SDK session that acts as a design critic.

```python
async def assess(url: str, cwd: str, deterministic_metrics: dict) -> dict:
    """Run subjective design assessment."""
    rubric = read_file("references/assessment-rubric.md")
    philosophy = read_file_if_exists(f"{cwd}/docs/ralph-lauren/philosophy.md")

    system_prompt = f"""You are an expert frontend design assessor.

{rubric}

{f"Current design system philosophy:\\n{philosophy}" if philosophy else "No design system established yet."}

Deterministic metrics already collected:
{json.dumps(deterministic_metrics, indent=2)}
"""

    prompt = f"""Assess the frontend at {url}.

1. Use agent-browser to navigate to {url} and take a full-page screenshot
2. Use agent-browser snapshot to analyze the DOM structure
3. Score each dimension (0-100) per the rubric
4. List specific findings with severity (P0-P3)
5. Provide actionable recommendations

Output your assessment as a JSON code block with this structure:
{{
  "scores": {{"heuristics": N, "typography": N, "layout": N, "color": N, "craft": N, "originality": N, "overall": N}},
  "findings": [{{"dimension": "...", "severity": "P0-P3", "description": "...", "recommendation": "..."}}],
  "summary": "2-3 sentence overall assessment"
}}"""

    result = await run_agent_session(
        prompt=prompt,
        system_prompt=system_prompt,
        tools=["Read", "Bash", "Glob", "Grep"],  # Bash for agent-browser
        cwd=cwd,
        permission_mode="default",  # read-only effectively
    )
    return parse_assessment_json(result)
```

**Key**: The assessor CANNOT edit files. It only reads and uses agent-browser via Bash.

## Step 4: Improver (`scripts/improver.py`)

Claude Agent SDK session that makes design improvements.

```python
async def improve(url: str, cwd: str, assessment: dict, iteration: int) -> str:
    """Run design improvement session."""
    philosophy = read_file_if_exists(f"{cwd}/docs/ralph-lauren/philosophy.md")

    system_prompt = f"""You are an expert frontend designer improving a web page.

{f"Design system philosophy (MUST follow for consistency):\\n{philosophy}" if philosophy else "No design system established yet. You will CREATE one."}

Rules:
- Fix issues by priority: P0 first, then P1, P2, P3
- Make targeted, surgical changes — don't rewrite entire files
- After making design system decisions (colors, fonts, spacing, etc.),
  UPDATE docs/ralph-lauren/philosophy.md with your choices and rationale
- philosophy.md must be PAGE-AGNOSTIC — document the design SYSTEM, not page-specific fixes
- Commit to specific values (e.g., "primary: #2563EB" not "use a blue")
"""

    prompt = f"""Improve the frontend at {url}.

Assessment (iteration {iteration}):
{json.dumps(assessment, indent=2)}

Focus on the highest-severity findings first. Make the changes, then verify
with agent-browser that they look correct.

After making changes, update docs/ralph-lauren/philosophy.md with any
design system decisions you made."""

    result = await run_agent_session(
        prompt=prompt,
        system_prompt=system_prompt,
        tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        cwd=cwd,
        permission_mode="acceptEdits",
    )
    return result
```

## Step 5: Main Orchestrator (`scripts/ralph_lauren.py`)

CLI entry point that runs the loop.

```python
#!/usr/bin/env python3
"""Ralph Lauren: Frontend Design Improvement Loop."""

import argparse, asyncio, json, os, shutil
from datetime import datetime
from pathlib import Path

async def main():
    args = parse_args()
    url = args.url
    cwd = args.cwd or os.getcwd()
    max_iters = args.max_iterations
    target = args.target_score

    # Setup output directory
    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = Path(cwd) / "docs" / "ralph-lauren" / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Ensure philosophy.md exists
    phil_path = Path(cwd) / "docs" / "ralph-lauren" / "philosophy.md"
    if not phil_path.exists():
        phil_path.parent.mkdir(parents=True, exist_ok=True)
        phil_path.write_text("# Design System Philosophy\n\n_Not yet established. Will be created during the first improvement iteration._\n")

    scores_history = []

    for i in range(1, max_iters + 1):
        iter_dir = run_dir / f"iteration-{i}"
        iter_dir.mkdir(exist_ok=True)

        # Step 1: Collect deterministic metrics
        print(f"\n{'='*60}")
        print(f"  ITERATION {i}/{max_iters}")
        print(f"{'='*60}")
        print(f"\n[1/4] Collecting deterministic metrics...")
        metrics = await collect_metrics(url)

        # Step 2: Run subjective assessment (separate Claude session)
        print(f"[2/4] Running subjective assessment...")
        assessment = await assess(url, cwd, metrics)

        # Save assessment
        (iter_dir / "assessment.json").write_text(json.dumps(assessment, indent=2))

        # Step 3: Take pre-improvement screenshot
        print(f"[3/4] Taking screenshot...")
        await take_screenshot(url, iter_dir / "screenshot.png")

        overall = assessment.get("scores", {}).get("overall", 0)
        scores_history.append({"iteration": i, "score": overall, "scores": assessment.get("scores", {})})
        print(f"      Score: {overall}/100 (target: {target})")

        # Check if target reached
        if overall >= target:
            print(f"\n  Target score {target} reached! Stopping.")
            break

        # Step 4: Run improvement session (separate Claude session)
        print(f"[4/4] Running improvement session...")
        changes = await improve(url, cwd, assessment, i)
        (iter_dir / "changes.md").write_text(changes)

    # Write summary
    write_summary(run_dir, scores_history, url, target)
    print(f"\nResults saved to: {run_dir}")
```

**CLI interface:**
```
usage: ralph_lauren.py [-h] --url URL [--cwd CWD]
                       [--max-iterations N] [--target-score N]

arguments:
  --url URL              Frontend URL to assess and improve
  --cwd CWD              Project working directory (default: cwd)
  --max-iterations N     Maximum improvement iterations (default: 5)
  --target-score N       Stop when overall score exceeds this (default: 85)
```

## Step 6: Skill & Command Files

### `skills/ralph-lauren/SKILL.md`
Documents the skill, its dependencies, and how it works.

### `commands/re/ralph-lauren.md`
```yaml
---
name: re:ralph-lauren
description: Run frontend design improvement loop — assess, improve, document, repeat
argument-hint: "<url> [--max-iterations N] [--target-score N]"
---
```

The command:
1. Checks dependencies (agent-browser, lighthouse, axe)
2. Parses arguments
3. Runs `python3 skills/ralph-lauren/scripts/ralph_lauren.py`
4. Streams output to the user

## Implementation Order

1. Assessment rubric (reference doc, no code)
2. metrics.py (pure Python, testable independently)
3. assessor.py (Claude Agent SDK, depends on rubric)
4. improver.py (Claude Agent SDK, depends on philosophy.md pattern)
5. ralph_lauren.py (orchestrator, depends on all above)
6. SKILL.md + command (wiring)

## Dependencies

- `claude-agent-sdk` (pip) — for spawning Claude sessions
- `agent-browser` (npm) — for screenshots and DOM inspection
- `lighthouse` (npm, optional) — for performance/a11y scores
- `axe-core/cli` (npm, optional) — for accessibility testing
- `anyio` (pip) — async runtime for claude-agent-sdk
