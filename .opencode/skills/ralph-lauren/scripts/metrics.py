"""Deterministic frontend metrics collection — Layer 1.

Collects Core Web Vitals (via agent-browser), Lighthouse scores, and CSS
statistics without involving any LLM — pure subprocess calls and parsing.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Core Web Vitals thresholds: (good_upper, needs_work_upper)
# Values beyond needs_work_upper are rated "poor".
# ---------------------------------------------------------------------------
_CWV_THRESHOLDS: dict[str, tuple[float, float]] = {
    "lcp": (2.5, 4.0),       # seconds
    "cls": (0.1, 0.25),      # unitless
    "fcp": (1.8, 3.0),       # seconds
    "ttfb": (0.8, 1.8),      # seconds
    "inp": (0.200, 0.500),   # seconds (200ms / 500ms)
}


def _rate(metric: str, value: float | None) -> str:
    if value is None:
        return "unknown"
    good, needs_work = _CWV_THRESHOLDS[metric]
    if value <= good:
        return "good"
    if value <= needs_work:
        return "needs-work"
    return "poor"


def _cwv_score(ratings: list[str]) -> int:
    """Average CWV ratings into a 0-100 score.

    Unknown/missing metrics count as 50 (needs-work) to avoid inflating
    the score when most metrics didn't fire.
    """
    score_map = {"good": 100, "needs-work": 50, "poor": 0, "unknown": 50}
    return round(sum(score_map.get(r, 50) for r in ratings) / len(ratings)) if ratings else 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def collect_metrics(url: str) -> dict[str, Any]:
    """Collect all deterministic metrics for a URL.

    Returns a dict with core_web_vitals, lighthouse, and css sections.
    Missing tools are skipped gracefully.
    """
    cwv, lighthouse, css = await asyncio.gather(
        collect_core_web_vitals(url),
        run_lighthouse(url),
        analyze_css(url),
    )
    return {
        "core_web_vitals": cwv,
        "lighthouse": lighthouse,
        "css": css,
    }


# ---------------------------------------------------------------------------
# Core Web Vitals via agent-browser
# ---------------------------------------------------------------------------

async def collect_core_web_vitals(url: str) -> dict[str, Any]:
    """Inject web-vitals library via agent-browser and read back CWV metrics.

    Flow: load page -> inject web-vitals IIFE from CDN -> register metric
    callbacks that write JSON to document.title -> wait -> read title back.
    """
    if not shutil.which("agent-browser"):
        return {"error": "agent-browser not found — skipping Core Web Vitals"}

    try:
        print("  Collecting Core Web Vitals...", flush=True)

        # Navigate to the target page
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "open", url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=15)

        # Inject web-vitals library with {reportAllChanges: true} so metrics
        # fire immediately instead of waiting for visibility change / interaction.
        inject_js = """
            (function() {
                window.__cwv = {};
                var s = document.createElement('script');
                s.src = 'https://unpkg.com/web-vitals@4/dist/web-vitals.iife.js';
                s.onload = function() {
                    var wv = webVitals;
                    var opts = {reportAllChanges: true};
                    function record(m) { window.__cwv[m.name.toLowerCase()] = m.value; }
                    wv.onLCP(record, opts);
                    wv.onCLS(record, opts);
                    wv.onFCP(record, opts);
                    wv.onTTFB(record, opts);
                    wv.onINP(record, opts);
                };
                document.head.appendChild(s);
            })();
        """.strip().replace("\n", " ")

        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "eval", inject_js,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)

        # Wait for initial metrics to fire
        await asyncio.sleep(2)

        # Scroll down and back to trigger LCP finalization and CLS measurement
        scroll_js = "window.scrollTo(0, document.body.scrollHeight); setTimeout(() => window.scrollTo(0, 0), 500);"
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "eval", scroll_js,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)
        await asyncio.sleep(2)

        # Write collected metrics to document.title so we can read them back
        flush_js = "document.title = JSON.stringify(window.__cwv || {});"
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "eval", flush_js,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=5)

        # Read title
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "get", "title",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        raw = stdout.decode().strip()

        # agent-browser returns double-encoded JSON strings
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, str):
                decoded = json.loads(decoded)
        except (json.JSONDecodeError, TypeError):
            decoded = {}

        return _build_cwv_result(decoded)

    except asyncio.TimeoutError:
        return {"error": "Core Web Vitals collection timed out"}
    except Exception as e:
        return {"error": f"Core Web Vitals failed: {e}"}


def _build_cwv_result(raw_metrics: dict[str, Any]) -> dict[str, Any]:
    """Transform raw web-vitals values into the structured output format."""
    result: dict[str, Any] = {}
    ratings: list[str] = []

    for metric in ("lcp", "cls", "fcp", "ttfb", "inp"):
        raw_val = raw_metrics.get(metric)
        if raw_val is not None:
            # web-vitals reports LCP/FCP/TTFB in ms, CLS unitless, INP in ms
            if metric in ("lcp", "fcp", "ttfb", "inp"):
                value = round(raw_val / 1000, 3)  # ms -> seconds
            else:
                value = round(raw_val, 4)
        else:
            value = None

        rating = _rate(metric, value)
        result[metric] = {"value": value, "rating": rating}
        ratings.append(rating)

    result["score"] = _cwv_score(ratings)
    return result


# ---------------------------------------------------------------------------
# Lighthouse
# ---------------------------------------------------------------------------

async def run_lighthouse(url: str) -> dict[str, Any] | None:
    """Run Lighthouse and return category scores."""
    if not shutil.which("npx"):
        return {"error": "npx not found — skipping Lighthouse"}

    print("  Running Lighthouse...", flush=True)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        output_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "--yes", "lighthouse", url,
            "--output=json",
            f"--output-path={output_path}",
            "--chrome-flags=--headless --no-sandbox --disable-gpu",
            "--quiet",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            return {"error": f"Lighthouse failed: {stderr.decode()[:500]}"}

        data = json.loads(Path(output_path).read_text())
        categories = data.get("categories", {})
        return {
            "performance": _score(categories.get("performance")),
            "accessibility": _score(categories.get("accessibility")),
            "best_practices": _score(categories.get("best-practices")),
            "seo": _score(categories.get("seo")),
        }
    except asyncio.TimeoutError:
        return {"error": "Lighthouse timed out after 120s"}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {"error": f"Lighthouse parse error: {e}"}
    finally:
        Path(output_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CSS analysis
# ---------------------------------------------------------------------------

async def analyze_css(url: str) -> dict[str, Any] | None:
    """Fetch page and analyze CSS statistics."""
    try:
        print("  Analyzing CSS...", flush=True)

        proc = await asyncio.create_subprocess_exec(
            "curl", "-sL", "--max-time", "15", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
        html = stdout.decode(errors="replace")

        # Extract inline styles
        style_blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL | re.IGNORECASE)
        all_css = "\n".join(style_blocks)

        # Extract linked stylesheet URLs and fetch them
        link_hrefs = re.findall(
            r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        )
        link_hrefs += re.findall(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\']',
            html, re.IGNORECASE,
        )

        for href in link_hrefs[:10]:
            resolved = _resolve_css_href(href, url)
            if resolved is None:
                continue
            try:
                css_proc = await asyncio.create_subprocess_exec(
                    "curl", "-sL", "--max-time", "10", resolved,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                css_stdout, _ = await asyncio.wait_for(css_proc.communicate(), timeout=15)
                all_css += "\n" + css_stdout.decode(errors="replace")
            except (asyncio.TimeoutError, Exception):
                continue

        if not all_css.strip():
            return {"note": "No CSS found (may be using CSS-in-JS)"}

        # Core stats
        colors = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", all_css))
        font_families = set(re.findall(r"font-family:\s*([^;}{]+)", all_css, re.IGNORECASE))
        font_sizes = re.findall(r"font-size:\s*([^;}{]+)", all_css, re.IGNORECASE)
        important_count = all_css.count("!important")
        selectors = re.findall(r"[^{}]+(?=\s*\{)", all_css)
        media_queries = re.findall(r"@media\s+[^{]+", all_css)

        # Unit analysis — px vs rem/em across all numeric declarations
        px_count = len(re.findall(r":\s*[^;{}]*[\d.]+px", all_css, re.IGNORECASE))
        rem_count = len(re.findall(r":\s*[^;{}]*[\d.]+rem", all_css, re.IGNORECASE))
        em_count = len(re.findall(r":\s*[^;{}]*[\d.]+em(?!s)", all_css, re.IGNORECASE))
        total_units = px_count + rem_count + em_count
        px_ratio = round(px_count / total_units, 2) if total_units > 0 else 0.0

        return {
            "total_css_bytes": len(all_css),
            "selector_count": len(selectors),
            "unique_hex_colors": len(colors),
            "hex_colors_sample": sorted(colors)[:20],
            "font_families": [f.strip().strip("'\"") for f in font_families][:10],
            "unique_font_sizes": len(set(s.strip() for s in font_sizes)),
            "important_count": important_count,
            "media_query_count": len(media_queries),
            "unit_analysis": {
                "px_count": px_count,
                "rem_count": rem_count,
                "em_count": em_count,
                "px_ratio": px_ratio,
            },
        }

    except Exception as e:
        return {"error": f"CSS analysis failed: {e}"}


def _resolve_css_href(href: str, base_url: str) -> str | None:
    """Resolve a stylesheet href to an absolute URL."""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    if href.startswith("http"):
        return href
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score(category: dict | None) -> float | None:
    """Extract score (0-100) from a Lighthouse category."""
    if not category:
        return None
    raw = category.get("score")
    if raw is not None:
        return round(raw * 100, 1)
    return None
