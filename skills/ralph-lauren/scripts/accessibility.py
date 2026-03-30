"""Deterministic accessibility checks via agent-browser JS injection.

Layer 2 of the frontend design assessment harness. Runs 15 concrete
accessibility checks by injecting JavaScript into the page — no LLM involved.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any


SEVERITY_P0 = "P0"
SEVERITY_P1 = "P1"
SEVERITY_P2 = "P2"

CHECK_SEVERITY: dict[str, str] = {
    "image_alt_text": SEVERITY_P0,
    "no_focus_removal": SEVERITY_P0,
    "color_contrast": SEVERITY_P0,
    "semantic_buttons": SEVERITY_P1,
    "form_labels": SEVERITY_P1,
    "no_placeholder_as_label": SEVERITY_P1,
    "focus_visible_styles": SEVERITY_P1,
    "reduced_motion": SEVERITY_P1,
    "aria_correctness": SEVERITY_P1,
    "heading_hierarchy": SEVERITY_P1,
    "form_structure": SEVERITY_P2,
    "dialog_element": SEVERITY_P2,
    "skip_link": SEVERITY_P2,
    "relative_units": SEVERITY_P2,
    "click_target_size": SEVERITY_P2,
}

# Single JS payload that runs all 15 checks and returns results as JSON.
# Each check produces {pass: bool, count: number, details: string}.
_JS_CHECKS = r"""
(function() {
  const results = {};

  // ── P0: image_alt_text ──────────────────────────────────────────────
  {
    const missing = document.querySelectorAll('img:not([alt])');
    const decorative = document.querySelectorAll('img[alt=""]');
    results.image_alt_text = {
      pass: missing.length === 0,
      count: missing.length,
      details: missing.length === 0
        ? `All images have alt attributes (${decorative.length} decorative)`
        : `${missing.length} image(s) missing alt: ${[...missing].slice(0, 5).map(i => i.src.split('/').pop()).join(', ')}`
    };
  }

  // ── P0: no_focus_removal ────────────────────────────────────────────
  {
    let violations = 0;
    const violatingSelectors = [];
    try {
      for (const sheet of document.styleSheets) {
        try {
          const rules = sheet.cssRules || sheet.rules;
          if (!rules) continue;
          for (const rule of rules) {
            if (rule.selectorText && rule.selectorText.includes(':focus')) {
              const style = rule.style;
              const removesOutline =
                style.getPropertyValue('outline') === 'none' ||
                style.getPropertyValue('outline') === '0' ||
                style.getPropertyValue('outline') === '0px' ||
                style.getPropertyValue('outline-style') === 'none' ||
                style.getPropertyValue('outline-width') === '0' ||
                style.getPropertyValue('outline-width') === '0px';
              if (removesOutline && !rule.selectorText.includes(':focus-visible')) {
                violations++;
                violatingSelectors.push(rule.selectorText);
              }
            }
            // Check inside media queries
            if (rule.cssRules) {
              for (const inner of rule.cssRules) {
                if (inner.selectorText && inner.selectorText.includes(':focus')) {
                  const s = inner.style;
                  const removes =
                    s.getPropertyValue('outline') === 'none' ||
                    s.getPropertyValue('outline') === '0' ||
                    s.getPropertyValue('outline') === '0px' ||
                    s.getPropertyValue('outline-style') === 'none' ||
                    s.getPropertyValue('outline-width') === '0' ||
                    s.getPropertyValue('outline-width') === '0px';
                  if (removes && !inner.selectorText.includes(':focus-visible')) {
                    violations++;
                    violatingSelectors.push(inner.selectorText);
                  }
                }
              }
            }
          }
        } catch(e) { /* cross-origin stylesheet, skip */ }
      }
    } catch(e) { /* no stylesheets */ }
    results.no_focus_removal = {
      pass: violations === 0,
      count: violations,
      details: violations === 0
        ? 'No focus outline removal detected'
        : `${violations} rule(s) remove focus outline: ${violatingSelectors.slice(0, 5).join('; ')}`
    };
  }

  // ── P0: color_contrast ──────────────────────────────────────────────
  {
    function luminance(r, g, b) {
      const a = [r, g, b].map(v => {
        v /= 255;
        return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
    }
    function parseColor(str) {
      const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      return m ? [+m[1], +m[2], +m[3]] : null;
    }
    function contrastRatio(fg, bg) {
      const l1 = luminance(...fg);
      const l2 = luminance(...bg);
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (lighter + 0.05) / (darker + 0.05);
    }
    function getEffectiveBg(el) {
      let current = el;
      while (current && current !== document.documentElement) {
        const bg = getComputedStyle(current).backgroundColor;
        const parsed = parseColor(bg);
        if (parsed && !(parsed[0] === 0 && parsed[1] === 0 && parsed[2] === 0 && bg.includes(',') && parseFloat(bg.split(',')[3]) === 0)) {
          const alpha = bg.includes(',') && bg.startsWith('rgba') ? parseFloat(bg.split(',')[3]) : 1;
          if (alpha > 0.1) return parsed;
        }
        current = current.parentElement;
      }
      return [255, 255, 255];
    }

    const textEls = document.querySelectorAll('p, span, a, li, h1, h2, h3, h4, h5, h6, td, th, label, button');
    const sampled = [...textEls].filter(el => el.offsetWidth > 0 && el.textContent.trim().length > 0).slice(0, 5);
    let failures = 0;
    const failDetails = [];
    for (const el of sampled) {
      const cs = getComputedStyle(el);
      const fg = parseColor(cs.color);
      const bg = getEffectiveBg(el);
      if (fg && bg) {
        const ratio = contrastRatio(fg, bg);
        if (ratio < 4.5) {
          failures++;
          failDetails.push(`"${el.textContent.trim().slice(0, 30)}" ratio=${ratio.toFixed(2)} (fg:rgb(${fg}) bg:rgb(${bg}))`);
        }
      }
    }
    results.color_contrast = {
      pass: failures === 0,
      count: failures,
      details: failures === 0
        ? `${sampled.length} sampled elements all meet 4.5:1`
        : `${failures}/${sampled.length} sampled elements below 4.5:1 — ${failDetails.join('; ')}`
    };
  }

  // ── P1: semantic_buttons ────────────────────────────────────────────
  {
    const bad = document.querySelectorAll('[onclick]:not(button):not(a):not(input):not([role="button"])');
    results.semantic_buttons = {
      pass: bad.length === 0,
      count: bad.length,
      details: bad.length === 0
        ? 'All onclick handlers are on semantic interactive elements'
        : `${bad.length} non-semantic element(s) with onclick: ${[...bad].slice(0, 5).map(e => `<${e.tagName.toLowerCase()}>`).join(', ')}`
    };
  }

  // ── P1: form_labels ─────────────────────────────────────────────────
  {
    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"])');
    let unlabeled = 0;
    const unlabeledNames = [];
    for (const input of inputs) {
      const hasLabel = input.id && document.querySelector(`label[for="${input.id}"]`);
      const wrappedInLabel = input.closest('label');
      const hasAriaLabel = input.getAttribute('aria-label') || input.getAttribute('aria-labelledby');
      if (!hasLabel && !wrappedInLabel && !hasAriaLabel) {
        unlabeled++;
        unlabeledNames.push(input.name || input.type || 'unnamed');
      }
    }
    results.form_labels = {
      pass: unlabeled === 0,
      count: unlabeled,
      details: unlabeled === 0
        ? `All ${inputs.length} visible inputs have labels`
        : `${unlabeled} input(s) without labels: ${unlabeledNames.slice(0, 5).join(', ')}`
    };
  }

  // ── P1: no_placeholder_as_label ─────────────────────────────────────
  {
    const inputs = document.querySelectorAll('input[placeholder]:not([type="hidden"]):not([type="submit"])');
    let violations = 0;
    const violationNames = [];
    for (const input of inputs) {
      const hasLabel = input.id && document.querySelector(`label[for="${input.id}"]`);
      const wrappedInLabel = input.closest('label');
      const hasAriaLabel = input.getAttribute('aria-label') || input.getAttribute('aria-labelledby');
      if (!hasLabel && !wrappedInLabel && !hasAriaLabel) {
        violations++;
        violationNames.push(input.placeholder.slice(0, 30));
      }
    }
    results.no_placeholder_as_label = {
      pass: violations === 0,
      count: violations,
      details: violations === 0
        ? 'No inputs rely solely on placeholder as label'
        : `${violations} input(s) use placeholder as only label: "${violationNames.slice(0, 3).join('", "')}"`
    };
  }

  // ── P1: focus_visible_styles ────────────────────────────────────────
  {
    let hasFocusVisible = false;
    try {
      for (const sheet of document.styleSheets) {
        try {
          const rules = sheet.cssRules || sheet.rules;
          if (!rules) continue;
          for (const rule of rules) {
            if (rule.selectorText && rule.selectorText.includes(':focus-visible')) {
              hasFocusVisible = true;
              break;
            }
            if (rule.cssRules) {
              for (const inner of rule.cssRules) {
                if (inner.selectorText && inner.selectorText.includes(':focus-visible')) {
                  hasFocusVisible = true;
                  break;
                }
              }
            }
            if (hasFocusVisible) break;
          }
        } catch(e) { /* cross-origin */ }
        if (hasFocusVisible) break;
      }
    } catch(e) {}
    results.focus_visible_styles = {
      pass: hasFocusVisible,
      count: hasFocusVisible ? 1 : 0,
      details: hasFocusVisible
        ? 'CSS contains :focus-visible rules'
        : 'No :focus-visible rules found in any stylesheet'
    };
  }

  // ── P1: reduced_motion ──────────────────────────────────────────────
  {
    let hasReducedMotion = false;
    try {
      for (const sheet of document.styleSheets) {
        try {
          const rules = sheet.cssRules || sheet.rules;
          if (!rules) continue;
          for (const rule of rules) {
            if (rule.conditionText && rule.conditionText.includes('prefers-reduced-motion')) {
              hasReducedMotion = true;
              break;
            }
            if (rule.media && rule.media.mediaText && rule.media.mediaText.includes('prefers-reduced-motion')) {
              hasReducedMotion = true;
              break;
            }
          }
        } catch(e) {}
        if (hasReducedMotion) break;
      }
    } catch(e) {}
    results.reduced_motion = {
      pass: hasReducedMotion,
      count: hasReducedMotion ? 1 : 0,
      details: hasReducedMotion
        ? 'CSS contains prefers-reduced-motion media query'
        : 'No prefers-reduced-motion media query found'
    };
  }

  // ── P1: aria_correctness ────────────────────────────────────────────
  {
    const nonInteractiveTags = ['DIV', 'SPAN', 'P', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 'MAIN', 'NAV', 'ASIDE'];
    const ariaLabeled = document.querySelectorAll('[aria-label]');
    let misuses = 0;
    const misuseTags = [];
    for (const el of ariaLabeled) {
      const tag = el.tagName;
      const role = el.getAttribute('role');
      const interactiveRoles = ['button', 'link', 'textbox', 'checkbox', 'radio', 'tab', 'menuitem', 'switch', 'combobox', 'searchbox', 'slider', 'spinbutton', 'option', 'navigation', 'search', 'dialog', 'alertdialog', 'tablist', 'toolbar', 'menu', 'region', 'landmark', 'img'];
      if (nonInteractiveTags.includes(tag) && (!role || !interactiveRoles.includes(role))) {
        misuses++;
        misuseTags.push(`<${tag.toLowerCase()} aria-label="${el.getAttribute('aria-label').slice(0, 25)}">`);
      }
    }
    results.aria_correctness = {
      pass: misuses === 0,
      count: misuses,
      details: misuses === 0
        ? `All ${ariaLabeled.length} aria-label usages are on interactive/landmark elements`
        : `${misuses} aria-label(s) on non-interactive elements: ${misuseTags.slice(0, 3).join(', ')}`
    };
  }

  // ── P1: heading_hierarchy ───────────────────────────────────────────
  {
    const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const levels = [...headings].map(h => parseInt(h.tagName[1]));
    const skips = [];
    for (let i = 1; i < levels.length; i++) {
      if (levels[i] > levels[i - 1] + 1) {
        skips.push(`h${levels[i - 1]}→h${levels[i]}`);
      }
    }
    results.heading_hierarchy = {
      pass: skips.length === 0,
      count: skips.length,
      details: skips.length === 0
        ? `${levels.length} headings in correct hierarchy`
        : `${skips.length} heading skip(s): ${skips.slice(0, 5).join(', ')}`
    };
  }

  // ── P2: form_structure ──────────────────────────────────────────────
  {
    const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]), select, textarea');
    let orphaned = 0;
    for (const input of inputs) {
      if (!input.closest('form')) orphaned++;
    }
    results.form_structure = {
      pass: orphaned === 0,
      count: orphaned,
      details: orphaned === 0
        ? `All ${inputs.length} form controls are inside <form> elements`
        : `${orphaned} form control(s) not inside a <form>`
    };
  }

  // ── P2: dialog_element ──────────────────────────────────────────────
  {
    const roleDialogs = document.querySelectorAll('[role="dialog"], [role="alertdialog"]');
    let nonNative = 0;
    const tags = [];
    for (const el of roleDialogs) {
      if (el.tagName !== 'DIALOG') {
        nonNative++;
        tags.push(`<${el.tagName.toLowerCase()} role="${el.getAttribute('role')}">`);
      }
    }
    results.dialog_element = {
      pass: nonNative === 0,
      count: nonNative,
      details: nonNative === 0
        ? roleDialogs.length === 0 ? 'No dialog roles found' : 'All dialog roles use native <dialog>'
        : `${nonNative} dialog role(s) not on native <dialog>: ${tags.slice(0, 3).join(', ')}`
    };
  }

  // ── P2: skip_link ───────────────────────────────────────────────────
  {
    const focusable = document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]');
    const first = focusable[0];
    let hasSkipLink = false;
    let skipDetails = 'No focusable elements found';
    if (first) {
      const href = first.getAttribute('href') || '';
      const text = first.textContent.trim().toLowerCase();
      hasSkipLink = (href.startsWith('#') && (text.includes('skip') || text.includes('main content') || text.includes('navigation')));
      skipDetails = hasSkipLink
        ? `Skip link found: "${first.textContent.trim().slice(0, 40)}"`
        : `First focusable element is <${first.tagName.toLowerCase()}>: "${first.textContent.trim().slice(0, 40)}" — not a skip link`;
    }
    results.skip_link = {
      pass: hasSkipLink,
      count: hasSkipLink ? 1 : 0,
      details: skipDetails
    };
  }

  // ── P2: relative_units ──────────────────────────────────────────────
  {
    let pxCount = 0;
    let relCount = 0;
    try {
      for (const sheet of document.styleSheets) {
        try {
          const rules = sheet.cssRules || sheet.rules;
          if (!rules) continue;
          const checkRules = (ruleList) => {
            for (const rule of ruleList) {
              if (rule.style) {
                const fs = rule.style.getPropertyValue('font-size');
                if (fs) {
                  if (fs.includes('px')) pxCount++;
                  else if (fs.includes('rem') || fs.includes('em') || fs.includes('%') || fs.includes('vw') || fs.includes('vh') || fs.includes('clamp')) relCount++;
                }
              }
              if (rule.cssRules) checkRules(rule.cssRules);
            }
          };
          checkRules(rules);
        } catch(e) {}
      }
    } catch(e) {}
    const total = pxCount + relCount;
    const pxPct = total > 0 ? Math.round(pxCount / total * 100) : 0;
    results.relative_units = {
      pass: total === 0 || pxPct <= 50,
      count: pxCount,
      details: total === 0
        ? 'No font-size declarations found in accessible stylesheets'
        : `${pxCount}px vs ${relCount}rem/em — ${pxPct}% pixel-based${pxPct > 50 ? ' (exceeds 50% threshold)' : ''}`
    };
  }

  // ── P2: click_target_size ───────────────────────────────────────────
  {
    const interactive = document.querySelectorAll('a, button, input, select, textarea, [role="button"], [role="link"], [tabindex]');
    const sampled = [...interactive].filter(el => el.offsetWidth > 0).slice(0, 20);
    let tooSmall = 0;
    const smallEls = [];
    for (const el of sampled) {
      const rect = el.getBoundingClientRect();
      if (rect.width < 44 || rect.height < 44) {
        // Inline text links get a pass on height if width is fine
        const isInlineLink = el.tagName === 'A' && el.closest('p, li, td, span');
        if (!isInlineLink) {
          tooSmall++;
          smallEls.push(`<${el.tagName.toLowerCase()}> ${Math.round(rect.width)}x${Math.round(rect.height)}px`);
        }
      }
    }
    results.click_target_size = {
      pass: tooSmall === 0,
      count: tooSmall,
      details: tooSmall === 0
        ? `${sampled.length} sampled interactive elements all meet 44x44px minimum`
        : `${tooSmall}/${sampled.length} elements below 44x44px: ${smallEls.slice(0, 5).join('; ')}`
    };
  }

  return JSON.stringify(results);
})()
""".strip()


async def run_accessibility_checks(url: str) -> dict[str, Any]:
    """Run 15 accessibility checks via agent-browser JS injection.

    Opens the URL, injects a single JS payload that performs all checks,
    and returns structured results with per-check pass/fail, an overall
    score, and severity classifications.
    """
    if not shutil.which("agent-browser"):
        return {
            "error": "agent-browser not installed",
            "checks": {},
            "score": 0,
            "summary": "Cannot run accessibility checks — agent-browser CLI not found",
        }

    try:
        # Navigate to the page
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "open", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            return {
                "error": f"Failed to open URL: {stderr.decode()[:300]}",
                "checks": {},
                "score": 0,
                "summary": f"agent-browser could not navigate to {url}",
            }

        # Wait for page load / JS execution
        await asyncio.sleep(2)

        # Inject the JS checks payload
        proc = await asyncio.create_subprocess_exec(
            "agent-browser", "eval", _JS_CHECKS,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

        if proc.returncode != 0:
            return {
                "error": f"JS eval failed: {stderr.decode()[:300]}",
                "checks": {},
                "score": 0,
                "summary": "Failed to execute accessibility checks JS",
            }

        raw = stdout.decode().strip()
        checks = _parse_eval_result(raw)

        if checks is None:
            return {
                "error": f"Could not parse eval output (length={len(raw)})",
                "raw_output": raw[:1000],
                "checks": {},
                "score": 0,
                "summary": "JS executed but result was not parseable",
            }

        return _build_result(checks)

    except asyncio.TimeoutError:
        return {
            "error": "Timed out waiting for agent-browser",
            "checks": {},
            "score": 0,
            "summary": "Accessibility checks timed out",
        }
    except Exception as e:
        return {
            "error": str(e),
            "checks": {},
            "score": 0,
            "summary": f"Unexpected error: {e}",
        }


def _parse_eval_result(raw: str) -> dict[str, Any] | None:
    """Parse the double-encoded JSON from agent-browser eval.

    agent-browser wraps eval output in a JSON string, so the result
    is a JSON string containing a JSON string containing our object.
    """
    # Try double-decode: JSON string wrapping a JSON string
    try:
        inner = json.loads(raw)
        if isinstance(inner, str):
            return json.loads(inner)
        if isinstance(inner, dict):
            return inner
    except (json.JSONDecodeError, TypeError):
        pass

    # Try single decode (some versions may not double-wrap)
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass

    # Try stripping surrounding quotes manually
    stripped = raw.strip().strip('"').strip("'")
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        pass

    return None


def _build_result(checks: dict[str, Any]) -> dict[str, Any]:
    """Transform raw check results into the final structured output."""
    total = len(CHECK_SEVERITY)
    passed = sum(1 for name in CHECK_SEVERITY if checks.get(name, {}).get("pass", False))
    score = round(passed / total * 100, 1) if total > 0 else 0

    by_severity: dict[str, list[dict[str, Any]]] = {
        SEVERITY_P0: [],
        SEVERITY_P1: [],
        SEVERITY_P2: [],
    }

    for name, severity in CHECK_SEVERITY.items():
        check = checks.get(name, {"pass": False, "count": 0, "details": "Check not found in results"})
        entry = {
            "name": name,
            "severity": severity,
            "pass": check.get("pass", False),
            "count": check.get("count", 0),
            "details": check.get("details", ""),
        }
        by_severity[severity].append(entry)

    failures = [
        entry
        for group in by_severity.values()
        for entry in group
        if not entry["pass"]
    ]

    p0_failures = sum(1 for f in failures if f["severity"] == SEVERITY_P0)
    p1_failures = sum(1 for f in failures if f["severity"] == SEVERITY_P1)
    p2_failures = sum(1 for f in failures if f["severity"] == SEVERITY_P2)

    summary_parts = []
    if p0_failures:
        summary_parts.append(f"{p0_failures} critical (P0)")
    if p1_failures:
        summary_parts.append(f"{p1_failures} major (P1)")
    if p2_failures:
        summary_parts.append(f"{p2_failures} minor (P2)")

    summary = (
        f"{passed}/{total} checks passed ({score}%). "
        + (f"Failures: {', '.join(summary_parts)}." if summary_parts else "All checks passed.")
    )

    return {
        "score": score,
        "passed": passed,
        "total": total,
        "checks": checks,
        "by_severity": by_severity,
        "failures": failures,
        "summary": summary,
    }


async def main() -> None:
    """CLI entry point for standalone testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Run 15 deterministic accessibility checks via agent-browser")
    parser.add_argument("url", help="URL to check")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output raw JSON")
    args = parser.parse_args()

    result = await run_accessibility_checks(args.url)

    if args.json_output:
        print(json.dumps(result, indent=2))
        return

    # Human-readable output
    if "error" in result and not result.get("checks"):
        print(f"ERROR: {result['error']}")
        return

    print(f"\nAccessibility Score: {result['score']}% ({result['passed']}/{result['total']} checks passed)\n")

    for severity in [SEVERITY_P0, SEVERITY_P1, SEVERITY_P2]:
        entries = result.get("by_severity", {}).get(severity, [])
        if not entries:
            continue
        print(f"── {severity} {'Critical' if severity == SEVERITY_P0 else 'Major' if severity == SEVERITY_P1 else 'Minor'} ──")
        for entry in entries:
            status = "PASS" if entry["pass"] else "FAIL"
            print(f"  [{status}] {entry['name']}: {entry['details']}")
        print()

    print(result["summary"])


if __name__ == "__main__":
    asyncio.run(main())
