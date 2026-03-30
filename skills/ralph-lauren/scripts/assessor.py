"""Subjective frontend design assessment via Claude Agent SDK.

Spawns an independent Claude session that uses agent-browser to screenshot
and inspect the page, then scores it against the assessment rubric.
This session is READ-ONLY — it cannot modify project files.
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
    screenshot_path: str | None = None,
    segmentation_paths: list[str] | None = None,
    iteration: int = 1,
    previous_changes: str | None = None,
    previous_scores: dict[str, Any] | None = None,
    focus: str | None = None,
) -> dict[str, Any]:
    """Run subjective design assessment in a separate Claude session.

    Args:
        url: The frontend URL to assess.
        cwd: Project working directory.
        deterministic_metrics: Results from metrics.py.
        screenshot_path: If provided, save the screenshot here.
        segmentation_paths: Paths to pre-generated segmentation maps.
        iteration: Current iteration number (1-based). Iterations 2+ use a faster protocol.
        previous_changes: Changes.md content from the previous iteration.
        previous_scores: Previous iteration's scores dict for comparison.
        focus: Optional focus point to emphasize in assessment.

    Returns:
        Parsed assessment dict with scores, findings, and summary.
    """
    is_followup = iteration > 1
    focus_context = ""
    if focus:
        focus_context = f"""

## USER FOCUS POINT (PRIORITY)

The user has asked to focus on: **{focus}**

This is your TOP PRIORITY. Score and evaluate this specific concern first,
then do the general assessment. Findings related to this focus should be
weighted more heavily and listed first."""
    rubric = RUBRIC_PATH.read_text()
    philosophy = _read_philosophy(cwd)
    metrics_json = json.dumps(deterministic_metrics, indent=2)
    screenshot_instruction = ""
    if screenshot_path:
        screenshot_instruction = f"\nSave the full-page screenshot to: {screenshot_path}"

    # Build segmentation context
    segmentation_context = ""
    if segmentation_paths:
        seg_list = "\n".join(f"   - {p}" for p in segmentation_paths)
        segmentation_context = f"""

## Pre-Generated Segmentation Maps

Segmentation maps have been generated for the screenshots using MobileSAM.
These color-coded overlays identify UI regions, components, spacing, and visual hierarchy.

IMPORTANT: You MUST examine these segmentation maps by reading them as images.
They are critical for your assessment — they reveal layout structure, spacing
inconsistencies, and component boundaries that may not be obvious from screenshots alone.

Segmentation map files:
{seg_list}

Use the Read tool to view each segmentation map image, then reference what you
see in your scoring and findings."""

    # Build previous iteration context
    prev_context = ""
    if is_followup and previous_changes:
        prev_scores_str = ""
        if previous_scores:
            prev_scores_str = f"""Previous scores: {json.dumps(previous_scores)}
Focus your assessment on dimensions that scored LOWEST — those need the most attention."""
        prev_context = f"""

## Previous Iteration Context

This is iteration {iteration}. The previous iteration made these changes:

{previous_changes}

{prev_scores_str}

IMPORTANT: Evaluate whether the previous changes ACTUALLY improved things.
If they made things worse, say so explicitly. If they helped, acknowledge it."""

    system_prompt = f"""You are an expert frontend design assessor performing a thorough, critical evaluation.
You combine the methodologies of two professional design assessment frameworks:

Your job is to assess the design quality of a web page — NOT to fix anything.
You MUST be honest and critical. Do not inflate scores.
{focus_context}
{"This is a FOLLOW-UP assessment (iteration " + str(iteration) + "). Be faster — skip full link validation and hover testing. Focus on re-scoring dimensions and evaluating whether previous changes helped." if is_followup else ""}

## Phase 1: /audit — Technical Quality Audit (impeccable.style)

Perform a structured technical audit across 5 dimensions. For each, assign a
severity rating (P0=critical, P1=major, P2=minor, P3=nit) to every finding:

1. **Normalize** — Does the implementation align with the design system (or lack thereof)?
   Check: token usage, component consistency, naming conventions, shared patterns.
2. **Harden** — Are error states, edge cases, and loading states handled?
   Check: empty states, long text overflow, missing images, error boundaries, skeleton screens.
3. **Optimize** — Are there performance issues visible in the frontend?
   Check: image sizes, layout shifts, render-blocking resources, unnecessary animations.
4. **Adapt** — Does the page handle its current viewport well?
   Check: responsive behavior, touch targets, text scaling, container queries.
5. **Clarify** — Is the UX copy clear and helpful?
   Check: button labels, error messages, empty state text, microcopy, CTAs.

## Phase 2: /critique — UX & Design Review (impeccable.style)

Score against Nielsen's 10 heuristics (each 0-10, total 0-100):
1. Visibility of system status
2. Match between system and real world
3. User control and freedom
4. Consistency and standards
5. Error prevention
6. Recognition rather than recall
7. Flexibility and efficiency of use
8. Aesthetic and minimalist design
9. Help users recognize, diagnose, recover from errors
10. Help and documentation

Then test with persona archetypes:
- **New user**: Can they understand the page in 5 seconds?
- **Power user**: Are there efficient paths and keyboard shortcuts?
- **Accessibility user**: Can they navigate with screen reader / keyboard only?

Assess cognitive load: Is information density appropriate? Too dense? Too sparse?

{segmentation_context}

## Phase 3: Detailed Dimension Scoring

{rubric}

## Design System Context

{f"The project has an established design philosophy:\\n\\n{philosophy}" if philosophy else "No design system has been established yet. Assess the page on its own merits."}

## Deterministic Metrics (already collected)

These are objective measurements. Use them to inform your subjective assessment:

```json
{metrics_json}
```
{prev_context}"""

    # Build the prompt — follow-up iterations are shorter
    if is_followup:
        prompt = f"""Assess the frontend design at: {url} (FOLLOW-UP iteration {iteration})

**Shortened Protocol — focus on re-scoring, not full exploration:**

1. Run: agent-browser open {url}
2. Take 2-3 viewport screenshots (hero + one scroll position)
   {screenshot_instruction}
3. Examine the segmentation maps if provided (Read tool)
4. Re-score ALL 6 dimensions (0-100) — compare against previous scores
5. Evaluate whether the previous iteration's changes improved things
6. List only NEW findings or findings that got WORSE
7. Skip full link validation (only check if previously-broken links were fixed)
8. Skip full hover testing (only check if previously-missing hover states were added)

Output the JSON assessment in the same format as before.
Be CRITICAL. If changes made things worse, the score should go DOWN."""
    else:
        prompt = f"""Assess the frontend design at: {url}

Follow this protocol exactly:

**Step 1: Visual Inspection (MULTIPLE SCREENSHOTS)**
1. Run: agent-browser open {url}
2. Take MULTIPLE viewport screenshots by scrolling through the page:
   - agent-browser screenshot screenshot-hero.png
   - agent-browser eval "window.scrollTo(0, 800)" && sleep 1
   - agent-browser screenshot screenshot-section1.png
   - agent-browser eval "window.scrollTo(0, 1600)" && sleep 1
   - agent-browser screenshot screenshot-section2.png
   - agent-browser eval "window.scrollTo(0, 2400)" && sleep 1
   - agent-browser screenshot screenshot-section3.png
   - agent-browser eval "window.scrollTo(0, document.body.scrollHeight)" && sleep 1
   - agent-browser screenshot screenshot-footer.png
   {screenshot_instruction}
3. Run: agent-browser snapshot -i
4. Examine ALL screenshots to see every section as a real user would (including scroll-triggered animations)

**Step 1b: Examine Segmentation Maps**
If segmentation maps were provided (listed in the system prompt above), you MUST:
1. Use the Read tool to view each segmentation map image file
2. Analyze what the segmentation reveals about layout structure, spacing consistency, component boundaries
3. Note any spacing irregularities, misaligned regions, or structural issues visible in the segmentation
4. Reference segmentation findings in your dimension scores (especially Layout and Craft)

**Step 1c: Link Validation**
Check EVERY link on the page:
1. Run: agent-browser snapshot -i --json (to get all interactive elements with refs)
2. For each link element, run: agent-browser get attr href @eN
3. For external links, run: curl -sI <url> | head -5 (check for 200, 301, 404, etc.)
4. For GitHub links, also fetch the page content and check for "404" in the title (GitHub returns 200 for 404 pages)
5. Report ALL broken links (404, 500), redirect chains, and placeholder '#' links as P0/P1 findings
6. Include a "links" section in the JSON output listing every link, its href, and its status (working/broken/redirect/placeholder)

**Step 1d: Hover State Assessment**
Test hover states on ALL interactive elements:
1. From the snapshot refs, identify all buttons, links, cards, and interactive elements
2. For each distinct interactive element TYPE (not every instance — pick one representative):
   - Run: agent-browser hover @eN
   - Wait briefly for CSS transitions to complete (sleep 0.5)
   - Run: agent-browser screenshot screenshot-hover-[element-type].png
   - Note: what changes on hover? (color, shadow, scale, underline, background, cursor, opacity?)
3. Assess the hover states:
   - Are hover effects consistent across similar elements?
   - Do all interactive elements HAVE hover states? (missing hover = P1)
   - Are transitions smooth (not instant)?
   - Do hover states provide clear affordance that the element is interactive?
   - Are focus-visible states present for keyboard users?
4. Include hover assessment findings in the main findings list with /polish or /delight skill tags

**Step 2: /audit — Technical Quality Audit**
Evaluate the 5 technical dimensions (normalize, harden, optimize, adapt, clarify).
List every finding with severity P0-P3.

**Step 3: /critique — UX & Design Review**
Score each of Nielsen's 10 heuristics (0-10).
Test against the 3 persona archetypes (new user, power user, accessibility user).
Assess cognitive load.

**Step 4: Dimension Scoring**
Score each of the 6 dimensions (0-100) per the rubric:
heuristics, typography, layout, color, craft, originality.

**Step 5: Synthesize**
Calculate the weighted overall score.
For each finding, recommend which impeccable skill would fix it:
- Typography issues → /typeset
- Layout/spacing issues → /arrange
- Needs more personality → /bolder, /delight
- Too loud/cluttered → /quieter, /distill
- Color issues → /colorize
- UX copy issues → /clarify
- Missing motion → /animate
- Onboarding/empty states → /onboard
- Error handling gaps → /harden
- Performance issues → /optimize
- Design system alignment → /normalize
- Final polish → /polish

Output your complete assessment as a single JSON code block with this structure:
{{
  "scores": {{
    "heuristics": 0, "typography": 0, "layout": 0,
    "color": 0, "craft": 0, "originality": 0, "overall": 0
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
  "audit": {{
    "normalize": ["findings..."],
    "harden": ["findings..."],
    "optimize": ["findings..."],
    "adapt": ["findings..."],
    "clarify": ["findings..."]
  }},
  "links": [
    {{
      "text": "link text",
      "href": "url or #",
      "status": "working|broken|redirect|placeholder",
      "http_code": 200
    }}
  ],
  "hover_assessment": {{
    "elements_tested": 0,
    "elements_with_hover": 0,
    "elements_missing_hover": 0,
    "consistency": "consistent|inconsistent|none",
    "transitions": "smooth|instant|missing",
    "findings": ["specific hover-related findings"]
  }},
  "findings": [
    {{
      "dimension": "layout",
      "severity": "P1",
      "description": "Specific issue",
      "recommendation": "Specific fix",
      "impeccable_skill": "/arrange"
    }}
  ],
  "summary": "2-3 sentence overall assessment"
}}

Remember: be CRITICAL, not encouraging. Most sites score 40-65. A score of 85+ means truly excellent."""

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
    """Read philosophy.md if it exists and has content."""
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
        return {
            "scores": {
                "heuristics": 0, "typography": 0, "layout": 0,
                "color": 0, "craft": 0, "originality": 0, "overall": 0,
            },
            "findings": [],
            "summary": "Assessment session returned no output — may have timed out or errored",
            "_parse_error": True,
        }

    # Strategy 1: JSON code block — use GREEDY match to capture the full block
    json_match = re.search(r"```(?:json)?\s*\n(\{.+\})\s*\n```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 2: Bracket-counting extraction from first { containing "scores"
    start = -1
    for i, ch in enumerate(text):
        if ch == '{' and '"scores"' in text[i:i+500]:
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

    # Strategy 3: Try the entire response as JSON
    try:
        return json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: return a structured error with the raw text
    return {
        "scores": {
            "heuristics": 0, "typography": 0, "layout": 0,
            "color": 0, "craft": 0, "originality": 0, "overall": 0,
        },
        "findings": [],
        "summary": f"Failed to parse assessment. Raw response length: {len(text)} chars",
        "_raw": text,
        "_parse_error": True,
    }


async def main():
    """CLI entry point for standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Run subjective design assessment")
    parser.add_argument("--url", required=True, help="URL to assess")
    parser.add_argument("--cwd", default=".", help="Project directory")
    args = parser.parse_args()

    result = await assess(args.url, args.cwd, {})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    anyio.run(main)
