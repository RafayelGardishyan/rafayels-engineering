"""Deterministic frontend metrics collection.

Collects Lighthouse scores, axe accessibility results, and CSS statistics
without involving any LLM — pure subprocess calls and HTML parsing.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


async def collect_metrics(url: str) -> dict[str, Any]:
    """Collect all deterministic metrics for a URL.

    Returns a dict with lighthouse, accessibility, and css sections.
    Missing tools are skipped gracefully.
    """
    lighthouse, axe, css = await asyncio.gather(
        run_lighthouse(url),
        run_axe(url),
        analyze_css(url),
    )
    return {
        "lighthouse": lighthouse,
        "accessibility": axe,
        "css": css,
    }


async def run_lighthouse(url: str) -> dict[str, Any] | None:
    """Run Lighthouse and return category scores."""
    if not shutil.which("npx"):
        return {"error": "npx not found — skipping Lighthouse"}

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


async def run_axe(url: str) -> dict[str, Any] | None:
    """Run axe accessibility scan via agent-browser's built-in Chrome.

    Uses agent-browser to inject axe-core into the page and run it,
    avoiding the ChromeDriver version mismatch issue with @axe-core/cli.
    Falls back to npx @axe-core/cli if agent-browser is unavailable.
    """
    # Strategy 1: Use agent-browser to inject and run axe-core directly
    if shutil.which("agent-browser"):
        try:
            # Inject axe-core from CDN and run it
            axe_script = (
                "const script = document.createElement('script');"
                "script.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js';"
                "script.onload = () => {"
                "  axe.run().then(r => {"
                "    document.title = JSON.stringify({violations: r.violations.length, "
                "      passes: r.passes.length, incomplete: r.incomplete.length, "
                "      details: r.violations.slice(0, 20).map(v => ({id: v.id, impact: v.impact, "
                "        description: v.description, nodes: v.nodes.length}))});"
                "  });"
                "};"
                "document.head.appendChild(script);"
            )

            # Open page and inject axe
            proc = await asyncio.create_subprocess_exec(
                "agent-browser", "open", url,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=15)

            proc = await asyncio.create_subprocess_exec(
                "agent-browser", "eval", axe_script,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10)

            # Wait for axe to complete
            await asyncio.sleep(5)

            # Read results from document.title
            proc = await asyncio.create_subprocess_exec(
                "agent-browser", "get", "title",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            title = stdout.decode().strip()

            try:
                data = json.loads(title)
                return {
                    "violations_count": data.get("violations", 0),
                    "passes_count": data.get("passes", 0),
                    "incomplete_count": data.get("incomplete", 0),
                    "violations": data.get("details", []),
                }
            except (json.JSONDecodeError, TypeError):
                return {"note": "axe-core injection ran but results not parseable"}

        except (asyncio.TimeoutError, Exception) as e:
            return {"error": f"axe via agent-browser failed: {e}"}

    # Strategy 2: Fall back to npx @axe-core/cli
    if not shutil.which("npx"):
        return {"error": "Neither agent-browser nor npx available — skipping axe"}

    try:
        proc = await asyncio.create_subprocess_exec(
            "npx", "--yes", "@axe-core/cli", url, "--stdout",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        output = stdout.decode()

        try:
            results = json.loads(output)
            if isinstance(results, list) and results:
                page = results[0]
                violations = page.get("violations", [])
                return {
                    "violations_count": len(violations),
                    "violations": [
                        {
                            "id": v["id"],
                            "impact": v.get("impact", "unknown"),
                            "description": v.get("description", ""),
                            "nodes_affected": len(v.get("nodes", [])),
                        }
                        for v in violations[:20]
                    ],
                    "passes_count": len(page.get("passes", [])),
                    "incomplete_count": len(page.get("incomplete", [])),
                }
        except json.JSONDecodeError:
            pass

        return {"raw_output": output[:2000]}

    except asyncio.TimeoutError:
        return {"error": "axe timed out after 60s"}
    except Exception as e:
        return {"error": f"axe failed: {e}"}


async def analyze_css(url: str) -> dict[str, Any] | None:
    """Fetch page and analyze CSS statistics."""
    try:
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
        # Also match href before rel
        link_hrefs += re.findall(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']stylesheet["\']',
            html, re.IGNORECASE,
        )

        for href in link_hrefs[:10]:  # cap at 10 stylesheets
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"
            elif not href.startswith("http"):
                continue

            try:
                css_proc = await asyncio.create_subprocess_exec(
                    "curl", "-sL", "--max-time", "10", href,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                css_stdout, _ = await asyncio.wait_for(css_proc.communicate(), timeout=15)
                all_css += "\n" + css_stdout.decode(errors="replace")
            except (asyncio.TimeoutError, Exception):
                continue

        if not all_css.strip():
            return {"note": "No CSS found (may be using CSS-in-JS)"}

        # Analyze
        colors = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", all_css))
        rgb_colors = re.findall(r"rgba?\([^)]+\)", all_css)
        hsl_colors = re.findall(r"hsla?\([^)]+\)", all_css)
        font_families = set(re.findall(r"font-family:\s*([^;}{]+)", all_css, re.IGNORECASE))
        font_sizes = re.findall(r"font-size:\s*([^;}{]+)", all_css, re.IGNORECASE)
        important_count = all_css.count("!important")
        selectors = re.findall(r"[^{}]+(?=\s*\{)", all_css)
        media_queries = re.findall(r"@media\s+[^{]+", all_css)

        return {
            "total_css_bytes": len(all_css),
            "selector_count": len(selectors),
            "unique_hex_colors": len(colors),
            "hex_colors_sample": sorted(colors)[:20],
            "rgb_color_count": len(set(rgb_colors)),
            "hsl_color_count": len(set(hsl_colors)),
            "font_families": [f.strip().strip("'\"") for f in font_families][:10],
            "unique_font_sizes": len(set(s.strip() for s in font_sizes)),
            "font_sizes_sample": sorted(set(s.strip() for s in font_sizes))[:15],
            "important_count": important_count,
            "media_query_count": len(media_queries),
        }

    except Exception as e:
        return {"error": f"CSS analysis failed: {e}"}


def _score(category: dict | None) -> float | None:
    """Extract score (0-100) from a Lighthouse category."""
    if not category:
        return None
    raw = category.get("score")
    if raw is not None:
        return round(raw * 100, 1)
    return None
