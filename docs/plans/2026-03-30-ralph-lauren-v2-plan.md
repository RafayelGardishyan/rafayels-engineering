---
date: 2026-03-30
topic: ralph-lauren-v2-assessment-rewrite
brainstorm: docs/brainstorms/2026-03-30-ralph-lauren-v2-brainstorm.md
---

# Implementation Plan: Ralph Lauren v2 Assessment Rewrite

## Overview

Rewrite 3 files, create 1 new file. Keep orchestrator and improver structure, replace assessment internals.

## Files to Change

```
skills/ralph-lauren/
├── scripts/
│   ├── metrics.py              # REWRITE — add CWV, restructure output
│   ├── accessibility.py        # NEW — Layer 2 DOM-based a11y checks
│   ├── assessor.py             # REWRITE — new rubric, layer 1+2 input, article 3 criteria
│   ├── ralph_lauren.py         # UPDATE — wire in accessibility.py
│   ├── improver.py             # UPDATE — NEVER/INSTEAD prompt structure
│   └── segmentation.py         # KEEP as-is
└── references/
    └── assessment-rubric.md    # REWRITE — research-backed criteria
```

## Step 1: Rewrite `metrics.py` (Layer 1)

Replace current Lighthouse-only approach with:

```python
async def collect_metrics(url: str) -> dict:
    return {
        "core_web_vitals": await collect_cwv(url),      # NEW: LCP, CLS, INP, FCP, TBT
        "lighthouse": await run_lighthouse(url),          # KEEP: category scores
        "css": await analyze_css(url),                    # UPDATE: add unit analysis (px vs rem)
    }
```

**Core Web Vitals collection** — inject `web-vitals` library via agent-browser:
```javascript
// Inject web-vitals CDN, collect LCP/CLS/FCP/INP/TTFB
import('https://unpkg.com/web-vitals@4?module').then(({onLCP, onCLS, onFCP, onINP, onTTFB}) => {
    const results = {};
    onLCP(m => results.lcp = m.value);
    onCLS(m => results.cls = m.value);
    // ... collect all, write to document.title
});
```

**CSS unit analysis** — count px vs rem/em usage:
```python
{
    "px_values": 45,        # count of px declarations
    "rem_values": 12,       # count of rem declarations
    "em_values": 3,
    "px_ratio": 0.75,       # px/(px+rem+em) — lower is better
}
```

**CWV thresholds** (from Google):
| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| LCP | ≤2.5s | ≤4.0s | >4.0s |
| CLS | ≤0.1 | ≤0.25 | >0.25 |
| INP | ≤200ms | ≤500ms | >500ms |
| FCP | ≤1.8s | ≤3.0s | >3.0s |
| TTFB | ≤800ms | ≤1800ms | >1800ms |

## Step 2: Create `accessibility.py` (Layer 2)

New file — 15 concrete DOM checks via agent-browser JS injection. No LLM.

Each check returns `{pass: bool, details: str, severity: "P0"|"P1"|"P2"}`.

**Checks (from article 2):**

1. **Semantic buttons** — `querySelectorAll('[onclick]:not(button):not(a)')` → P1 if found
2. **Form structure** — every `<input>` inside a `<form>` with submit button → P1
3. **Label association** — every `<input>` has `<label for="">` matching its `id` → P1
4. **No placeholder-as-label** — inputs with placeholder but no label → P1
5. **Image alt text** — every `<img>` has `alt` attribute → P0
6. **Focus visible** — CSS contains `:focus-visible` rules → P1
7. **No focus removal** — CSS doesn't contain `outline: none` on `:focus` without replacement → P0
8. **Dialog usage** — modals use `<dialog>` not `<div role="dialog">` → P2
9. **Skip link** — first focusable element is a skip-to-content link → P2
10. **Reduced motion** — CSS contains `prefers-reduced-motion` media query → P1
11. **Relative units** — font-size declarations use rem/em not px (ratio check) → P2
12. **Color contrast** — text elements meet 4.5:1 ratio (sample check) → P0
13. **ARIA misuse** — `aria-label` not on non-interactive elements → P1
14. **Heading hierarchy** — h1→h2→h3 without skipping levels → P2
15. **Click target size** — interactive elements ≥ 44x44px → P2

**Output:**
```python
{
    "score": 73,          # percentage of checks passed
    "passed": 11,
    "failed": 4,
    "checks": [
        {"name": "semantic_buttons", "pass": True, "severity": "P1", "details": "..."},
        ...
    ]
}
```

## Step 3: Rewrite `assessment-rubric.md`

Replace 6 ad-hoc dimensions with 6 research-backed ones:

**1. Performance (15%, deterministic)**
- Scored from CWV thresholds: all good = 100, all poor = 0
- Formula: average of per-metric scores (good=100, needs-improvement=50, poor=0)

**2. Accessibility (20%, deterministic)**
- Scored from Layer 2 check pass rate + Lighthouse a11y score
- Formula: `(layer2_score * 0.6) + (lighthouse_a11y * 0.4)`

**3. Visual Polish & Coherence (20%, subjective)**
From article 3 + impeccable.style:
- Typography system: consistent scale, hierarchy, line heights, font pairing
- Spacing system: consistent rhythm, alignment, whitespace
- Color system: cohesive palette, contrast, semantic usage
- Craft details: radii, shadows, transitions, hover states consistency

**4. UX & Usability (20%, subjective)**
From article 2 + Nielsen:
- Navigation clarity, information architecture
- Interactive element affordance (do buttons look clickable?)
- Error states, loading states, empty states
- Form usability, keyboard navigation

**5. Aesthetic Fit (10%, subjective)**
From article 3:
- Does the design match its stated purpose and audience?
- Is the aesthetic direction committed and consistent?
- Do typography, color, and layout serve the same mood?

**6. Creative Distinction (15%, subjective)**
From article 3:
- NEVER: generic fonts (Inter, Roboto), purple gradients, predictable card grids
- INSTEAD: distinctive type choices, committed palettes, surprising layouts
- Does it have personality? Would you remember it?

## Step 4: Rewrite `assessor.py`

- Receive Layer 1 (metrics) + Layer 2 (accessibility) as pre-computed data
- Focus the Claude session on Layer 3 subjective criteria only
- Use article 3's evaluation methodology in the prompt
- Reduced scope = fewer turns needed = faster

**System prompt structure:**
```
You are scoring 4 subjective design dimensions.
Layers 1+2 (performance + accessibility) are already scored deterministically.

[Layer 1+2 results as context]
[Segmentation maps to examine]
[Philosophy.md if exists]
[Previous iteration changes if follow-up]
[Focus point if provided]

Score these 4 dimensions (0-100 each):
1. Visual Polish & Coherence — [specific criteria from rubric]
2. UX & Usability — [specific criteria]
3. Aesthetic Fit — [specific criteria]
4. Creative Distinction — [NEVER/INSTEAD criteria]
```

**Key change**: assessor no longer scores performance or accessibility — those come from deterministic layers. The overall score is computed by the orchestrator combining all 6.

## Step 5: Update `ralph_lauren.py`

Wire in the new layer:
```python
# Step 1: Deterministic metrics (Layer 1)
metrics = await collect_metrics(url)

# Step 2: Screenshots + segmentation
await take_screenshot(url, ...)
await generate_segmentation_for_dir(...)

# Step 3: Accessibility checks (Layer 2) — NEW
a11y = await run_accessibility_checks(url)

# Step 4: Subjective assessment (Layer 3)
assessment = await assess(url, cwd, metrics, a11y, ...)

# Step 5: Compute overall score (combine all layers)
overall = compute_overall_score(metrics, a11y, assessment)
```

## Step 6: Update `improver.py`

Replace vague instructions with NEVER/INSTEAD structure from article 3:

```
## Typography
NEVER: Default to Inter, Roboto, or system fonts. Use random font sizes.
INSTEAD: Choose a distinctive display font. Establish a type scale. Work the
full typographic range (size, weight, case, spacing) for hierarchy.

## Color
NEVER: Use a safe, evenly-distributed palette. Default to purple gradients.
INSTEAD: Lead with a dominant color. Punctuate with sharp accents. Choose a
direction: bold & saturated, moody & restrained, or high-contrast & minimal.

## Layout
NEVER: Default to centered card grids. Use predictable symmetric layouts.
INSTEAD: Use intentional asymmetry. Break the grid where it serves the content.
Create visual flow through contrast in density and whitespace.
```

## Implementation Order

1. `assessment-rubric.md` — new criteria (reference doc, no code)
2. `accessibility.py` — NEW Layer 2 DOM checks
3. `metrics.py` — add CWV collection, CSS unit analysis
4. `assessor.py` — new prompts, receives layer 1+2 data
5. `ralph_lauren.py` — wire in accessibility.py, compute overall score
6. `improver.py` — NEVER/INSTEAD prompt structure
