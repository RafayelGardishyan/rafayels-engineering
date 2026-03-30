#!/usr/bin/env python3
"""Ralph Lauren: Frontend Design Improvement Loop.

A Python harness that runs an autonomous evaluate-improve loop on frontend pages.
Inspired by Anthropic's GAN-like evaluator/generator pattern.

Usage:
    python ralph_lauren.py --url http://localhost:3000 --cwd /path/to/project
    python ralph_lauren.py --url http://localhost:3000 --max-iterations 3 --target-score 90
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Force unbuffered output so harness progress shows in real time
os.environ["PYTHONUNBUFFERED"] = "1"

# Ensure script directory is on path for sibling imports
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from accessibility import run_accessibility_checks
from assessor import assess
from improver import improve
from metrics import collect_metrics
from segmentation import generate_segmentation_for_dir


def _print(msg: str) -> None:
    """Print with flush for real-time output."""
    print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ralph Lauren: Frontend Design Improvement Loop",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url http://localhost:3000
  %(prog)s --url http://localhost:5173 --max-iterations 3 --target-score 90
  %(prog)s --url http://localhost:3000/dashboard --cwd ~/projects/myapp
        """,
    )
    parser.add_argument(
        "--url", required=True,
        help="Frontend URL to assess and improve",
    )
    parser.add_argument(
        "--cwd", default=None,
        help="Project working directory (default: current directory)",
    )
    parser.add_argument(
        "--max-iterations", type=int, default=5,
        help="Maximum improvement iterations (default: 5)",
    )
    parser.add_argument(
        "--target-score", type=int, default=85,
        help="Stop when overall score exceeds this (default: 85)",
    )
    parser.add_argument(
        "--skip-deterministic", action="store_true",
        help="Skip Lighthouse/axe metrics (faster, subjective-only)",
    )
    parser.add_argument(
        "--focus", default=None,
        help="Focus point for assessment and improvement (e.g., 'Fix spacing and overlap issues')",
    )
    return parser.parse_args()


async def take_screenshot(url: str, output_path: Path) -> bool:
    """Take multiple viewport screenshots by scrolling through the page.

    Instead of one full-page screenshot (which misses scroll-triggered animations),
    takes a series of viewport-sized screenshots at different scroll positions.
    """
    if not shutil.which("agent-browser"):
        _print("      [warn] agent-browser not found — skipping screenshot")
        return False

    try:
        # Open the page
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "open", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=30)

        # Take screenshots at multiple scroll positions
        scroll_positions = [0, 800, 1600, 2400]
        stem = output_path.stem
        parent = output_path.parent
        suffix = output_path.suffix

        for i, scroll_y in enumerate(scroll_positions):
            # Scroll to position
            await _run_agent_browser("eval", f"window.scrollTo(0, {scroll_y})")
            await asyncio.sleep(1)  # wait for scroll animations to trigger

            # Screenshot this viewport
            shot_path = parent / f"{stem}-{i}{suffix}"
            await _run_agent_browser("screenshot", str(shot_path))

        # Also scroll to bottom for footer
        await _run_agent_browser("eval", "window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
        await _run_agent_browser("screenshot", str(parent / f"{stem}-footer{suffix}"))

        return True
    except (asyncio.TimeoutError, Exception) as e:
        _print(f"      [warn] Screenshot failed: {e}")
        return False


async def _run_agent_browser(*args: str) -> None:
    """Run an agent-browser command."""
    proc = await asyncio.create_subprocess_exec(
        "agent-browser", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(proc.communicate(), timeout=15)


def write_summary(
    run_dir: Path,
    scores_history: list[dict],
    url: str,
    target: int,
) -> None:
    """Write a summary markdown file for the run."""
    lines = [
        "# Ralph Lauren Run Summary",
        "",
        f"- **URL**: {url}",
        f"- **Target Score**: {target}",
        f"- **Iterations**: {len(scores_history)}",
        f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Score Progression",
        "",
        "| Iter | Overall | Perf | A11y | Polish | UX | Fit | Distinction |",
        "|------|---------|------|------|--------|----|-----|-------------|",
    ]

    for entry in scores_history:
        s = entry.get("scores", {})
        lines.append(
            f"| {entry['iteration']} "
            f"| **{s.get('overall', '?')}** "
            f"| {s.get('performance', '?')} "
            f"| {s.get('accessibility', '?')} "
            f"| {s.get('visual_polish', '?')} "
            f"| {s.get('ux_usability', '?')} "
            f"| {s.get('aesthetic_fit', '?')} "
            f"| {s.get('creative_distinction', '?')} |"
        )

    if len(scores_history) >= 2:
        first = scores_history[0].get("scores", {}).get("overall", 0)
        last = scores_history[-1].get("scores", {}).get("overall", 0)
        delta = last - first
        lines.extend([
            "",
            f"## Result",
            "",
            f"- **Starting score**: {first}",
            f"- **Final score**: {last}",
            f"- **Improvement**: {'+' if delta >= 0 else ''}{delta} points",
            f"- **Target {'reached' if last >= target else 'not reached'}**",
        ])

    lines.append("")
    (run_dir / "summary.md").write_text("\n".join(lines))


def check_dependencies() -> list[str]:
    """Check for required and optional dependencies."""
    warnings = []

    # Required
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        _print("ERROR: claude-agent-sdk not installed.")
        _print("  Install with: pip install claude-agent-sdk")
        sys.exit(1)

    # Optional
    if not shutil.which("agent-browser"):
        warnings.append("agent-browser not found (npm i -g agent-browser) — screenshots will be limited")
    if not shutil.which("npx"):
        warnings.append("npx not found — Lighthouse and axe metrics will be skipped")

    return warnings


def print_banner(url: str, max_iters: int, target: int) -> None:
    _print("")
    _print("  ┌─────────────────────────────────────────┐")
    _print("  │         RALPH LAUREN                     │")
    _print("  │    Frontend Design Improvement Loop      │")
    _print("  └─────────────────────────────────────────┘")
    _print("")
    _print(f"  URL:            {url}")
    _print(f"  Max iterations: {max_iters}")
    _print(f"  Target score:   {target}/100")
    _print("")


async def run() -> None:
    args = parse_args()
    url = args.url
    cwd = args.cwd or str(Path.cwd())
    max_iters = args.max_iterations
    target = args.target_score
    skip_deterministic = args.skip_deterministic
    focus = args.focus

    # Check dependencies
    warnings = check_dependencies()
    for w in warnings:
        _print(f"  [warn] {w}")

    if focus:
        _print(f"  Focus:          {focus}")
    print_banner(url, max_iters, target)

    # Setup output directory
    run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    run_dir = Path(cwd) / "docs" / "ralph-lauren" / f"run-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Ensure philosophy.md exists
    phil_path = Path(cwd) / "docs" / "ralph-lauren" / "philosophy.md"
    if not phil_path.exists():
        phil_path.parent.mkdir(parents=True, exist_ok=True)
        phil_path.write_text(
            "# Design System Philosophy\n\n"
            "_Not yet established. Will be created during the first improvement iteration._\n"
        )

    scores_history = []
    previous_changes = None
    previous_scores = None

    for i in range(1, max_iters + 1):
        iter_dir = run_dir / f"iteration-{i}"
        iter_dir.mkdir(exist_ok=True)
        is_followup = i > 1

        _print(f"\n{'='*60}")
        _print(f"  ITERATION {i}/{max_iters}{'  (follow-up — faster protocol)' if is_followup else ''}")
        _print(f"{'='*60}")

        # Step 1: Layer 1 — Deterministic metrics (skip on follow-ups)
        metrics = {}
        if not skip_deterministic and not is_followup:
            _print(f"\n  [1/7] Layer 1: Collecting deterministic metrics...")
            metrics = await collect_metrics(url)
            (iter_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
            _print_metrics_summary(metrics)
        else:
            _print(f"\n  [1/7] Layer 1: Skipped {'(follow-up)' if is_followup else '(--skip-deterministic)'}")

        # Step 2: Layer 2 — Accessibility DOM checks
        a11y = {}
        if not is_followup:
            _print(f"\n  [2/7] Layer 2: Running accessibility checks...")
            a11y = await run_accessibility_checks(url)
            (iter_dir / "accessibility.json").write_text(json.dumps(a11y, indent=2))
            a11y_score = a11y.get("score", 0)
            passed = a11y.get("passed", 0)
            failed = a11y.get("failed", 0)
            _print(f"         A11y: {passed}/{passed + failed} checks passed (score: {a11y_score})")
        else:
            _print(f"\n  [2/7] Layer 2: Skipped (follow-up)")

        # Step 3: Take screenshots
        _print(f"\n  [3/7] Taking viewport screenshots...")
        await take_screenshot(url, iter_dir / "screenshot.png")

        # Step 4: Generate segmentation maps
        _print(f"\n  [4/7] Generating segmentation maps...")
        await generate_segmentation_for_dir(iter_dir, url=url)
        segmentation_paths = sorted(iter_dir.glob("*-segmentation.png"))
        _print(f"         Generated {len(segmentation_paths)} segmentation maps")

        # Step 5: Layer 3 — Subjective assessment (Claude session)
        if is_followup:
            _print(f"\n  [5/7] Layer 3: Follow-up assessment (reviewing previous changes)...")
        else:
            _print(f"\n  [5/7] Layer 3: Full subjective assessment (hover + link testing)...")
        assessment = await assess(
            url, cwd, metrics, a11y,
            screenshot_path=str(iter_dir / "screenshot.png"),
            segmentation_paths=[str(p) for p in segmentation_paths],
            iteration=i,
            previous_changes=previous_changes,
            previous_scores=previous_scores,
            focus=focus,
        )
        (iter_dir / "assessment.json").write_text(json.dumps(assessment, indent=2))

        # Compute combined overall score (all 6 dimensions)
        overall, all_scores = _compute_overall(metrics, a11y, assessment)
        scores_history.append({
            "iteration": i,
            "score": overall,
            "scores": all_scores,
        })

        _print_assessment_summary(all_scores, assessment)

        # Step 6: Check if target reached
        if overall >= target:
            _print(f"\n  Target score {target} reached with {overall}! Stopping.")
            break

        # Step 6: Run improvement (independent Claude session)
        _print(f"\n  [6/7] Running improvement session...")
        changes = await improve(url, cwd, assessment, i, focus=focus)
        (iter_dir / "changes.md").write_text(f"# Iteration {i} Changes\n\n{changes}")

        # Save context for next iteration
        previous_changes = changes
        previous_scores = all_scores

        # Step 7: Post-improvement screenshots
        _print(f"\n  [7/7] Taking post-improvement screenshots...")
        await take_screenshot(url, iter_dir / "screenshot-after.png")

    # Write summary
    write_summary(run_dir, scores_history, url, target)

    _print(f"\n{'='*60}")
    _print(f"  RUN COMPLETE")
    _print(f"{'='*60}")
    _print(f"\n  Results:    {run_dir}")
    _print(f"  Summary:    {run_dir / 'summary.md'}")
    _print(f"  Philosophy: {phil_path}")

    if len(scores_history) >= 2:
        first = scores_history[0]["score"]
        last = scores_history[-1]["score"]
        _print(f"\n  Score: {first} → {last} ({'+' if last >= first else ''}{last - first})")

    _print("")


def _compute_overall(
    metrics: dict, a11y: dict, assessment: dict
) -> tuple[int, dict[str, Any]]:
    """Combine deterministic (Layer 1+2) and subjective (Layer 3) scores.

    Weights: performance=15%, accessibility=20%, visual_polish=20%,
             ux_usability=20%, aesthetic_fit=10%, creative_distinction=15%

    Returns (overall_score, all_scores_dict).
    """
    # Layer 1: Performance from CWV
    cwv = metrics.get("core_web_vitals", {})
    perf_score = cwv.get("score", 0) if isinstance(cwv, dict) and "error" not in cwv else 0

    # Layer 2: Accessibility from DOM checks + Lighthouse a11y
    a11y_dom_score = a11y.get("score", 0) if isinstance(a11y, dict) and "error" not in a11y else 0
    lh_a11y = 0
    lh = metrics.get("lighthouse", {})
    if isinstance(lh, dict) and "error" not in lh:
        lh_a11y = lh.get("accessibility", 0) or 0
    a11y_score = round(a11y_dom_score * 0.6 + lh_a11y * 0.4)

    # Layer 3: Subjective scores
    subj = assessment.get("subjective_scores", {})
    visual_polish = subj.get("visual_polish", 0)
    ux_usability = subj.get("ux_usability", 0)
    aesthetic_fit = subj.get("aesthetic_fit", 0)
    creative_distinction = subj.get("creative_distinction", 0)

    overall = round(
        perf_score * 0.15
        + a11y_score * 0.20
        + visual_polish * 0.20
        + ux_usability * 0.20
        + aesthetic_fit * 0.10
        + creative_distinction * 0.15
    )

    all_scores = {
        "overall": overall,
        "performance": perf_score,
        "accessibility": a11y_score,
        "visual_polish": visual_polish,
        "ux_usability": ux_usability,
        "aesthetic_fit": aesthetic_fit,
        "creative_distinction": creative_distinction,
    }
    return overall, all_scores


def _print_metrics_summary(metrics: dict) -> None:
    """Print a compact summary of deterministic metrics."""
    cwv = metrics.get("core_web_vitals", {})
    if isinstance(cwv, dict) and "error" not in cwv:
        parts = []
        for m in ("lcp", "cls", "fcp", "ttfb"):
            entry = cwv.get(m, {})
            if isinstance(entry, dict) and entry.get("value") is not None:
                parts.append(f"{m}={entry['value']}({entry['rating'][0]})")
        if parts:
            _print(f"         CWV: {', '.join(parts)} → score={cwv.get('score', '?')}")

    lh = metrics.get("lighthouse", {})
    if isinstance(lh, dict) and "error" not in lh:
        parts = [f"{k}={v}" for k, v in lh.items() if v is not None and k != "error"]
        if parts:
            _print(f"         Lighthouse: {', '.join(parts)}")

    css = metrics.get("css", {})
    if isinstance(css, dict) and "selector_count" in css:
        units = css.get("unit_analysis", {})
        px_ratio = units.get("px_ratio", "?")
        _print(f"         CSS: {css['selector_count']} selectors, {css.get('unique_hex_colors', '?')} colors, px_ratio={px_ratio}")


def _print_assessment_summary(all_scores: dict, assessment: dict) -> None:
    """Print combined scores summary."""
    overall = all_scores.get("overall", "?")
    _print(f"\n  Combined scores (6 dimensions):")
    _print(f"    Overall:              {overall}/100")
    _print(f"    Performance (det):    {all_scores.get('performance', '?')}/100")
    _print(f"    Accessibility (det):  {all_scores.get('accessibility', '?')}/100")
    _print(f"    Visual Polish (subj): {all_scores.get('visual_polish', '?')}/100")
    _print(f"    UX & Usability (subj):{all_scores.get('ux_usability', '?')}/100")
    _print(f"    Aesthetic Fit (subj): {all_scores.get('aesthetic_fit', '?')}/100")
    _print(f"    Creative Dist (subj): {all_scores.get('creative_distinction', '?')}/100")

    findings = assessment.get("findings", [])
    by_severity = {}
    for f in findings:
        sev = f.get("severity", "?")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    if by_severity:
        _print(f"    Findings: {', '.join(f'{k}={v}' for k, v in sorted(by_severity.items()))}")

    summary = assessment.get("summary", "")
    if summary:
        _print(f"    Summary: {summary[:140]}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
