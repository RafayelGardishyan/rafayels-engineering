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
        "--gemini-key", default=None,
        help="Gemini API key for segmentation maps (or set GEMINI_API_KEY env var)",
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
        "| Iteration | Overall | Heuristics | Typography | Layout | Color | Craft | Originality |",
        "|-----------|---------|------------|------------|--------|-------|-------|-------------|",
    ]

    for entry in scores_history:
        s = entry.get("scores", {})
        lines.append(
            f"| {entry['iteration']} "
            f"| **{s.get('overall', '?')}** "
            f"| {s.get('heuristics', '?')} "
            f"| {s.get('typography', '?')} "
            f"| {s.get('layout', '?')} "
            f"| {s.get('color', '?')} "
            f"| {s.get('craft', '?')} "
            f"| {s.get('originality', '?')} |"
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

    # Set Gemini key if provided via CLI
    if args.gemini_key:
        os.environ["GEMINI_API_KEY"] = args.gemini_key

    # Check dependencies
    warnings = check_dependencies()
    for w in warnings:
        _print(f"  [warn] {w}")

    if not os.environ.get("GEMINI_API_KEY"):
        _print("  [info] No GEMINI_API_KEY — segmentation maps will be skipped")

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

    for i in range(1, max_iters + 1):
        iter_dir = run_dir / f"iteration-{i}"
        iter_dir.mkdir(exist_ok=True)

        _print(f"\n{'='*60}")
        _print(f"  ITERATION {i}/{max_iters}")
        _print(f"{'='*60}")

        # Step 1: Deterministic metrics
        metrics = {}
        if not skip_deterministic:
            _print(f"\n  [1/5] Collecting deterministic metrics...")
            metrics = await collect_metrics(url)
            (iter_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
            _print_metrics_summary(metrics)
        else:
            _print(f"\n  [1/5] Skipping deterministic metrics (--skip-deterministic)")

        # Step 2: Subjective assessment (independent Claude session)
        _print(f"\n  [2/5] Running subjective assessment (with hover testing)...")
        screenshot_path = str(iter_dir / "screenshot.png")
        assessment = await assess(url, cwd, metrics, screenshot_path)
        (iter_dir / "assessment.json").write_text(json.dumps(assessment, indent=2))

        overall = assessment.get("scores", {}).get("overall", 0)
        scores_history.append({
            "iteration": i,
            "score": overall,
            "scores": assessment.get("scores", {}),
        })

        _print_assessment_summary(assessment)

        # Step 2b: Generate segmentation maps for all screenshots
        _print(f"\n  [2b/5] Generating segmentation maps...")
        await generate_segmentation_for_dir(iter_dir)

        # Step 3: Check if target reached
        if overall >= target:
            _print(f"\n  Target score {target} reached with {overall}! Stopping.")
            _print(f"\n  [3/5] Taking final screenshot...")
            await take_screenshot(url, iter_dir / "screenshot-final.png")
            await generate_segmentation_for_dir(iter_dir)
            break

        # Step 4: Run improvement (independent Claude session)
        _print(f"\n  [3/5] Running improvement session...")
        changes = await improve(url, cwd, assessment, i)
        (iter_dir / "changes.md").write_text(f"# Iteration {i} Changes\n\n{changes}")

        # Step 5: Post-improvement screenshots + segmentation
        _print(f"\n  [4/5] Taking post-improvement screenshots...")
        await take_screenshot(url, iter_dir / "screenshot-after.png")

        _print(f"\n  [5/5] Generating post-improvement segmentation maps...")
        await generate_segmentation_for_dir(iter_dir)

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


def _print_metrics_summary(metrics: dict) -> None:
    """Print a compact summary of deterministic metrics."""
    lh = metrics.get("lighthouse", {})
    if isinstance(lh, dict) and "error" not in lh:
        parts = []
        for key in ("performance", "accessibility", "best_practices", "seo"):
            val = lh.get(key)
            if val is not None:
                parts.append(f"{key}={val}")
        if parts:
            _print(f"         Lighthouse: {', '.join(parts)}")

    axe = metrics.get("accessibility", {})
    if isinstance(axe, dict) and "violations_count" in axe:
        _print(f"         Axe: {axe['violations_count']} violations, {axe.get('passes_count', '?')} passes")

    css = metrics.get("css", {})
    if isinstance(css, dict) and "selector_count" in css:
        _print(f"         CSS: {css['selector_count']} selectors, {css['unique_hex_colors']} colors, {css.get('important_count', 0)} !important")


def _print_assessment_summary(assessment: dict) -> None:
    """Print a compact summary of the subjective assessment."""
    scores = assessment.get("scores", {})
    overall = scores.get("overall", "?")
    _print(f"\n  Assessment scores:")
    _print(f"    Overall:     {overall}/100")
    for dim in ("heuristics", "typography", "layout", "color", "craft", "originality"):
        val = scores.get(dim, "?")
        _print(f"    {dim:12s}: {val}/100")

    findings = assessment.get("findings", [])
    by_severity = {}
    for f in findings:
        sev = f.get("severity", "?")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    if by_severity:
        parts = [f"{k}={v}" for k, v in sorted(by_severity.items())]
        _print(f"    Findings:    {', '.join(parts)}")

    # Print link validation results
    links = assessment.get("links", [])
    broken = [l for l in links if l.get("status") in ("broken", "placeholder")]
    if broken:
        _print(f"    Broken links: {len(broken)}")

    # Print hover assessment
    hover = assessment.get("hover_assessment", {})
    if hover:
        _print(f"    Hover states: {hover.get('elements_with_hover', '?')}/{hover.get('elements_tested', '?')} elements")

    summary = assessment.get("summary", "")
    if summary:
        _print(f"    Summary:     {summary[:120]}")


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
