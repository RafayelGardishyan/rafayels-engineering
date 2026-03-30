"""Frontend design improvement via Claude Agent SDK.

Spawns an independent Claude session that reads the assessment report and
philosophy.md, then makes targeted code changes to improve the design.
This session has FULL edit permissions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def improve(
    url: str,
    cwd: str,
    assessment: dict[str, Any],
    iteration: int,
    focus: str | None = None,
) -> str:
    """Run design improvement in a separate Claude session.

    Args:
        url: The frontend URL being improved.
        cwd: Project working directory (where code lives).
        assessment: The assessment dict from assessor.py.
        iteration: Current iteration number.
        focus: Optional focus point from the user.

    Returns:
        Summary of changes made (text).
    """
    philosophy = _read_philosophy(cwd)
    assessment_json = json.dumps(assessment, indent=2)

    # Build skill-specific instructions based on assessment findings
    skill_instructions = _build_skill_instructions(assessment)

    system_prompt = f"""You are an expert frontend designer making targeted improvements to a web page.
You apply the impeccable.style methodology: each fix maps to a specific design skill.

## Your Mission

Fix the issues identified in the assessment, prioritized by severity (P0 first).
Make surgical, targeted changes — do not rewrite entire files.
{f"""
## USER FOCUS POINT (TOP PRIORITY)

The user specifically wants you to focus on: **{focus}**

Address this FIRST, before other findings. Even if the assessment doesn't mention it,
inspect the page for this specific concern and fix any issues you find.""" if focus else ""}

## Design System Philosophy

{f"You MUST follow this established design system for consistency:\\n\\n{philosophy}" if philosophy else "No design system exists yet. You will CREATE one during this iteration."}

## Impeccable Design Skills Reference

Apply these skills in order of the assessment findings:

### /typeset — Fix Typography
- Establish a consistent type scale (e.g., 12/14/16/20/24/32/40/48px)
- Set proper line heights (1.4-1.6 body, 1.1-1.3 headings)
- Ensure line lengths are 45-75 characters for body text
- Use max 2 font families, with clear roles (headings vs body)
- Use font weight purposefully (400 body, 500-600 medium emphasis, 700 headings)

### /arrange — Fix Layout & Spacing
- Establish a spacing scale (4/8/12/16/24/32/48/64px)
- Apply consistent grid alignment
- Fix padding/margin inconsistencies
- Ensure proper whitespace rhythm between sections
- Fix alignment issues (elements off by 1-2px)

### /colorize — Fix Color System
- Define a cohesive palette: primary, secondary, accent, neutral scale
- Ensure WCAG AA contrast ratios (4.5:1 normal text, 3:1 large text)
- Use semantic colors: success/warning/error/info
- Limit unique colors — consolidate similar shades
- Define hover/active/focus state colors

### /normalize — Align with Design System
- Make all components follow the same patterns
- Consolidate inconsistent border-radii, shadows, and transitions
- Ensure button styles, input styles, card styles are uniform

### /harden — Error Handling & Edge Cases
- Add loading/skeleton states
- Handle empty states gracefully
- Handle long text overflow (truncation, wrapping)
- Handle missing images with fallbacks

### /bolder — Amplify Timid Designs
- Increase visual hierarchy contrast
- Make CTAs more prominent
- Add visual weight where needed

### /quieter — Tone Down Loud Designs
- Reduce visual noise
- Simplify overly complex sections
- Remove unnecessary decorations

### /distill — Strip to Essence
- Remove unnecessary elements
- Simplify information architecture
- Reduce cognitive load

### /polish — Final Pass
- Fix micro-interactions (hover states, focus rings, transitions)
- Ensure consistent border-radii and shadow system
- Add subtle transitions (150-300ms) for state changes

### /clarify — Fix UX Copy
- Make button labels action-oriented
- Improve error messages to be helpful and specific
- Write clear empty state descriptions

### /delight — Add Personality
- Add subtle, purposeful animations
- Use color and typography to create mood
- Make the design feel intentional, not generic

## Critical Rules — MANDATORY

### Rule 0: philosophy.md (NON-NEGOTIABLE)

Your VERY FIRST action must be to read `docs/ralph-lauren/philosophy.md`.
Your VERY LAST action before finishing must be to update `docs/ralph-lauren/philosophy.md`.

If philosophy.md says "_Not yet established_" or is empty, you MUST create the design system
from scratch before making any visual changes. Write it first, then implement based on it.

The file MUST contain these sections with EXACT values (not placeholders):

```markdown
# Design System Philosophy

## Color Palette
- Primary: #XXXXXX (role description)
- Secondary: #XXXXXX
- Accent: #XXXXXX
- Neutrals: #XXX, #XXX, #XXX, #XXX, #XXX (lightest to darkest)
- Semantic: success=#XXX, warning=#XXX, error=#XXX, info=#XXX

## Typography
- Display: [font family] — used for [where]
- Body: [font family] — used for [where]
- Mono: [font family] — used for [where]
- Scale: [exact sizes in px or rem]
- Weights: [which weights for what purpose]
- Line heights: [exact values]

## Spacing
- Scale: [exact px values, e.g., 4/8/12/16/24/32/48/64]
- Section padding: [value]
- Component gap: [value]
- Card padding: [value]

## Components
- Border radius: [small/medium/large values]
- Shadows: [elevation levels with exact values]
- Transitions: [duration and easing]
- Focus ring: [style]
```

This file is PAGE-AGNOSTIC — it describes the design SYSTEM, not page-specific fixes.

### Other Rules

1. **Follow the philosophy** — if values are defined in philosophy.md, USE THEM exactly
2. **Verify with agent-browser** — after making changes, verify they look correct
3. **Fix by priority** — P0 first, then P1, P2, P3"""

    prompt = f"""Improve the frontend at: {url}

## Assessment (Iteration {iteration})

```json
{assessment_json}
```

## Skill-Specific Fix Plan

Based on the assessment findings, apply these impeccable skills in this order:

{skill_instructions}

## Execution Steps

1. Read the current codebase to understand the structure (use Glob and Read)
2. Fix issues by priority: P0 > P1 > P2 > P3
3. For each fix:
   a. Identify which impeccable skill applies (see findings above)
   b. Read the relevant file
   c. Apply the skill's methodology to make the targeted edit
   d. If you made a design system decision, update docs/ralph-lauren/philosophy.md
4. After all fixes, verify with agent-browser:
   - Run: agent-browser open {url}
   - Run: agent-browser screenshot --full verification.png
   - Check that your changes look correct
5. Summarize what you changed and which skills you applied

Focus on the HIGHEST IMPACT changes first. You don't need to fix everything —
fix the most impactful issues within a reasonable scope."""

    result_text = ""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=cwd,
            allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
            permission_mode="acceptEdits",
            max_turns=35,
        ),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result

    return result_text or "No changes reported."


def _build_skill_instructions(assessment: dict[str, Any]) -> str:
    """Build skill-specific fix instructions from assessment findings."""
    findings = assessment.get("findings", [])
    if not findings:
        return "No specific findings — apply /polish for general improvement."

    # Group findings by impeccable skill
    by_skill: dict[str, list[dict]] = {}
    for f in findings:
        skill = f.get("impeccable_skill", "/polish")
        by_skill.setdefault(skill, []).append(f)

    # Sort skills by highest severity finding
    severity_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

    def skill_priority(item: tuple[str, list[dict]]) -> int:
        return min(severity_order.get(f.get("severity", "P3"), 3) for f in item[1])

    lines = []
    for skill, skill_findings in sorted(by_skill.items(), key=skill_priority):
        lines.append(f"### {skill}")
        for f in sorted(skill_findings, key=lambda x: severity_order.get(x.get("severity", "P3"), 3)):
            sev = f.get("severity", "?")
            desc = f.get("description", "")
            rec = f.get("recommendation", "")
            lines.append(f"- **[{sev}]** {desc}")
            if rec:
                lines.append(f"  Fix: {rec}")
        lines.append("")

    return "\n".join(lines) if lines else "Apply /polish for general improvement."


def _read_philosophy(cwd: str) -> str | None:
    """Read philosophy.md if it exists and has content."""
    path = Path(cwd) / "docs" / "ralph-lauren" / "philosophy.md"
    if not path.exists():
        return None
    content = path.read_text().strip()
    if "_Not yet established" in content:
        return None
    return content


async def main():
    """CLI entry point for standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Run design improvement session")
    parser.add_argument("--url", required=True, help="URL to improve")
    parser.add_argument("--cwd", default=".", help="Project directory")
    parser.add_argument("--assessment", required=True, help="Path to assessment JSON")
    parser.add_argument("--iteration", type=int, default=1)
    args = parser.parse_args()

    assessment = json.loads(Path(args.assessment).read_text())
    result = await improve(args.url, args.cwd, assessment, args.iteration)
    print(result)


if __name__ == "__main__":
    anyio.run(main)
