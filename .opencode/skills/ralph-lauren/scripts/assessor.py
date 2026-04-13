"""Subjective frontend design assessment via Claude Agent SDK — Layer 3.

Scores 4 subjective dimensions: Visual Polish, UX & Usability, Aesthetic Fit,
and Creative Distinction. Receives pre-computed deterministic results (CWV,
accessibility checks) as context so the LLM focuses on what it's good at.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


SCRIPT_DIR = Path(__file__).parent
RUBRIC_PATH = SCRIPT_DIR.parent / "references" / "assessment-rubric.md"


async def assess(
    url: str,
    cwd: str,
    deterministic_metrics: dict[str, Any],
    accessibility_results: dict[str, Any],
    screenshot_path: str | None = None,
    segmentation_paths: list[str] | None = None,
    iteration: int = 1,
    previous_changes: str | None = None,
    previous_scores: dict[str, Any] | None = None,
    focus: str | None = None,
) -> dict[str, Any]:
    """Run subjective design assessment in a separate Claude session.

    Only scores dimensions 3-6 (Visual Polish, UX, Aesthetic Fit, Creative
    Distinction). Dimensions 1-2 (Performance, Accessibility) are scored
    deterministically by the orchestrator.
    """
    is_followup = iteration > 1
    rubric = RUBRIC_PATH.read_text()
    philosophy = _read_philosophy(cwd)
    metrics_json = json.dumps(deterministic_metrics, indent=2)
    a11y_json = json.dumps(accessibility_results, indent=2)

    # Build segmentation context
    seg_context = ""
    if segmentation_paths:
        seg_list = "\n".join(f"   - {p}" for p in segmentation_paths)
        seg_context = f"""
## Segmentation Maps (pre-generated)

DOM-based segmentation maps show element boundaries, types, and positions.
Examine them with the Read tool to understand layout structure and spacing.

Files:
{seg_list}
"""

    # Build focus context
    focus_context = ""
    if focus:
        focus_context = f"""
## USER FOCUS POINT (TOP PRIORITY)

The user specifically wants: **{focus}**

Evaluate this FIRST. Findings related to this focus should be listed first
and weighted more heavily in your scores."""

    # Build previous iteration context
    prev_context = ""
    if is_followup and previous_changes:
        prev_scores_str = json.dumps(previous_scores, indent=2) if previous_scores else "N/A"
        prev_context = f"""
## Previous Iteration

Changes made last iteration:
{previous_changes[:2000]}

Previous subjective scores: {prev_scores_str}

IMPORTANT: Evaluate whether these changes IMPROVED things. If they made
things worse, say so. If they helped, acknowledge it."""

    system_prompt = f"""You are an expert frontend design assessor scoring 4 SUBJECTIVE dimensions.

Performance and Accessibility are already scored by deterministic tools.
You focus ONLY on what requires human/AI judgment: visual quality, usability,
aesthetic direction, and creative distinction.
{focus_context}
{"This is a FOLLOW-UP iteration (" + str(iteration) + "). Be faster — skip full link/hover testing, focus on re-scoring and evaluating previous changes." if is_followup else ""}

## Your 4 Dimensions

### Dimension 3: Visual Polish & Coherence (0-100)
- Typography: consistent scale, hierarchy, line heights, font pairing, weight usage
- Spacing: consistent rhythm, proportional padding/margins, intentional whitespace
- Color: cohesive limited palette, dominant + accent structure, semantic colors, state colors
- Craft: consistent radii, shadows, transitions, hover states, edge case handling

### Dimension 4: UX & Usability (0-100)
Score each of Nielsen's 10 heuristics (0-10), total = UX score:
1. Visibility of system status
2. Match between system and real world
3. User control and freedom
4. Consistency and standards
5. Error prevention
6. Recognition rather than recall
7. Flexibility and efficiency of use
8. Aesthetic and minimalist design
9. Error recognition, diagnosis, recovery
10. Help and documentation

Also check: Can a new user understand in 5 seconds? Are CTAs obvious? Do interactive elements look interactive?

### Dimension 5: Aesthetic Fit (0-100)
- Is there a clear, committed aesthetic direction?
- Does every element serve that direction?
- Do typography, color, layout create a unified mood?
- Does the design feel made FOR this specific content?

### Dimension 6: Creative Distinction (0-100)
NEVER: Inter/Roboto/Arial as primary font, purple gradients, predictable card grids, cookie-cutter hero→features→pricing layout, gratuitous rounded corners, same look as every AI-generated page.
INSTEAD: distinctive typography, committed color palette, surprising layouts, bespoke details, memorable personality.

## Pre-Computed Deterministic Results (read-only context)

### Core Web Vitals & Lighthouse (Layer 1):
```json
{metrics_json}
```

### Accessibility Checks (Layer 2):
```json
{a11y_json}
```
{seg_context}

## Design System Context
{f"Established design philosophy:\\n{philosophy}" if philosophy else "No design system established yet."}
{prev_context}

## Rubric Reference
{rubric}"""

    # Build the prompt
    if is_followup:
        prompt = f"""Re-assess the frontend at: {url} (follow-up iteration {iteration})

FASTER PROTOCOL:
1. Open the page with agent-browser, take 2 screenshots (hero + one scroll)
2. Examine segmentation maps if available (Read tool)
3. Re-score all 4 subjective dimensions
4. Evaluate whether previous changes improved things
5. List only NEW or WORSENED findings

Output JSON assessment."""
    else:
        prompt = f"""Assess the frontend at: {url}

FULL PROTOCOL:
1. Open the page: agent-browser open {url}
2. Take viewport screenshots at multiple scroll positions:
   - agent-browser screenshot screenshot-hero.png
   - agent-browser eval "window.scrollTo(0, 800)" && sleep 1
   - agent-browser screenshot screenshot-section1.png
   - agent-browser eval "window.scrollTo(0, 1600)" && sleep 1
   - agent-browser screenshot screenshot-section2.png
   - agent-browser eval "window.scrollTo(0, 2400)" && sleep 1
   - agent-browser screenshot screenshot-section3.png
3. Get interactive snapshot: agent-browser snapshot -i
4. Examine segmentation maps (Read tool on each file)
5. CHECK ALL LINKS:
   - Get hrefs: agent-browser get attr href @eN for each link
   - Test external links: curl -sI <url> | head -3
   - For GitHub links, also check page content for "404"
   - Report broken/placeholder links
6. TEST HOVER STATES on representative elements:
   - agent-browser hover @eN → sleep 0.5 → agent-browser screenshot
   - Check: do all interactive elements HAVE hover states?
   - Are transitions smooth? Are focus-visible styles present?
7. Score all 4 subjective dimensions (0-100)
8. List ALL findings with severity and NEVER/INSTEAD recommendations

OUTPUT FORMAT — a single JSON code block:
{{
  "subjective_scores": {{
    "visual_polish": 0,
    "ux_usability": 0,
    "aesthetic_fit": 0,
    "creative_distinction": 0
  }},
  "nielsen_heuristics": {{
    "visibility_of_system_status": 0,
    "match_real_world": 0,
    "user_control": 0,
    "consistency": 0,
    "error_prevention": 0,
    "recognition_over_recall": 0,
    "flexibility": 0,
    "aesthetic_minimalism": 0,
    "error_recovery": 0,
    "help_documentation": 0
  }},
  "links": [
    {{"text": "...", "href": "...", "status": "working|broken|redirect|placeholder"}}
  ],
  "hover_assessment": {{
    "elements_tested": 0,
    "elements_with_hover": 0,
    "consistency": "consistent|inconsistent|none",
    "transitions": "smooth|instant|missing"
  }},
  "findings": [
    {{
      "dimension": "visual_polish|ux_usability|aesthetic_fit|creative_distinction",
      "severity": "P0|P1|P2|P3",
      "description": "Specific issue",
      "recommendation": "NEVER: [what to avoid]. INSTEAD: [what to do].",
      "impeccable_skill": "/typeset|/arrange|/colorize|/polish|/bolder|/delight|..."
    }}
  ],
  "summary": "2-3 sentence assessment"
}}

Be CRITICAL. Most sites score 45-65. A score of 85+ means truly excellent."""

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=cwd,
            allowed_tools=["Read", "Bash", "Glob", "Grep"],
            permission_mode="default",
            max_turns=30 if is_followup else 50,
        ),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""

    return _parse_assessment(result_text)


def _read_philosophy(cwd: str) -> str | None:
    path = Path(cwd) / "docs" / "ralph-lauren" / "philosophy.md"
    if not path.exists():
        return None
    content = path.read_text().strip()
    if "_Not yet established" in content:
        return None
    return content


def _parse_assessment(text: str | None) -> dict[str, Any]:
    """Extract JSON assessment from Claude's response."""
    if not text:
        return _empty_assessment("Session returned no output")

    # Strategy 1: JSON code block (greedy match)
    json_match = re.search(r"```(?:json)?\s*\n(\{.+\})\s*\n```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: Bracket-counting from first { containing "subjective_scores"
    start = -1
    for i, ch in enumerate(text):
        if ch == '{' and '"subjective_scores"' in text[i:i+500]:
            start = i
            break

    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        pass
                    break

    # Strategy 3: Whole text as JSON
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        pass

    return _empty_assessment(f"Failed to parse. Response length: {len(text)} chars", text)


def _empty_assessment(reason: str, raw: str | None = None) -> dict[str, Any]:
    return {
        "subjective_scores": {
            "visual_polish": 0, "ux_usability": 0,
            "aesthetic_fit": 0, "creative_distinction": 0,
        },
        "findings": [],
        "summary": reason,
        "_parse_error": True,
        **({"_raw": raw} if raw else {}),
    }


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run subjective design assessment")
    parser.add_argument("--url", required=True)
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()
    result = await assess(args.url, args.cwd, {}, {})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    anyio.run(main)
