# Frontend Design Assessment Rubric v2

Research-backed scoring criteria derived from:
- Core Web Vitals and frontend performance metrics
- Accessibility essentials for front-end developers
- Empirically-validated AI frontend evaluation methodology

## Scoring Overview

| # | Dimension | Layer | Weight | Source |
|---|-----------|-------|--------|--------|
| 1 | Performance | Deterministic (CWV) | 15% | Core Web Vitals thresholds |
| 2 | Accessibility | Deterministic (DOM) | 20% | 15-point a11y checklist |
| 3 | Visual Polish & Coherence | Subjective (Claude) | 20% | impeccable.style + article 3 |
| 4 | UX & Usability | Subjective (Claude) | 20% | Nielsen heuristics + article 2 |
| 5 | Aesthetic Fit | Subjective (Claude) | 10% | Article 3 evaluation criteria |
| 6 | Creative Distinction | Subjective (Claude) | 15% | Article 3 NEVER/INSTEAD |

**Overall** = `perf*0.15 + a11y*0.20 + polish*0.20 + ux*0.20 + fit*0.10 + distinction*0.15`

---

## Dimension 1: Performance (15%, Deterministic)

Scored automatically from Core Web Vitals. No LLM involved.

| Metric | Good (100pts) | Needs Work (50pts) | Poor (0pts) |
|--------|---------------|--------------------| ------------|
| LCP | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| CLS | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| INP | ≤ 200ms | ≤ 500ms | > 500ms |
| FCP | ≤ 1.8s | ≤ 3.0s | > 3.0s |
| TTFB | ≤ 800ms | ≤ 1800ms | > 1800ms |

**Score** = average of per-metric scores (each 0/50/100 based on thresholds).

Supplemented by Lighthouse category scores as additional context.

---

## Dimension 2: Accessibility (20%, Deterministic)

Scored from 15 concrete DOM checks + Lighthouse accessibility score.

**Formula**: `(dom_check_pass_rate * 60) + (lighthouse_a11y * 0.4)`

### The 15 Checks (from accessibility essentials research)

**P0 — Critical (blocks screen reader users):**
1. **Image alt text** — every `<img>` has `alt` attribute (empty `alt=""` OK for decorative)
2. **No focus removal** — no `outline: none` on `:focus` without `:focus-visible` replacement
3. **Color contrast** — sampled text/background combinations meet WCAG AA 4.5:1

**P1 — Major (significantly harms usability):**
4. **Semantic buttons** — no `<div onclick>` or `<span onclick>` as sole interactive elements
5. **Form labels** — every `<input>` has `<label for="">` with matching `id`
6. **No placeholder-as-label** — inputs with `placeholder` also have a proper `<label>`
7. **Focus visible styles** — CSS includes `:focus-visible` rules
8. **Reduced motion** — CSS includes `@media (prefers-reduced-motion: reduce)`
9. **ARIA correctness** — `aria-label` only on interactive elements, not on `<div>` or `<span>`
10. **Heading hierarchy** — heading levels don't skip (h1→h2→h3, not h1→h3)

**P2 — Minor (best practice):**
11. **Form structure** — inputs wrapped in `<form>` with submit mechanism
12. **Dialog element** — modals use `<dialog>` not `<div role="dialog">`
13. **Skip link** — first focusable element is a skip-to-content link
14. **Relative units** — font-size uses rem/em over px (>50% ratio)
15. **Click target size** — interactive elements ≥ 44x44 CSS pixels

---

## Dimension 3: Visual Polish & Coherence (20%, Subjective)

The Claude assessor scores this based on:

### Typography System
- Is there a consistent, intentional type scale (not random sizes)?
- Does display type carry the design's voice while body text stays legible?
- Are font weights used purposefully to establish hierarchy?
- Is the full typographic range used (size, weight, case, spacing)?
- Line heights: 1.4-1.6 body, 1.1-1.3 headings?
- Line lengths: 45-75 characters for body text?

### Spacing System
- Is there a consistent spacing scale (e.g., 4/8/12/16/24/32/48/64)?
- Are padding and margins proportional and rhythmic?
- Is whitespace used intentionally — not too cramped, not too sparse?
- Do component gaps follow a predictable pattern?

### Color System
- Is the palette cohesive and deliberately limited?
- Does it lead with a dominant color, punctuated by sharp accents?
- Are neutrals well-chosen and consistent?
- Are semantic colors present (success/warning/error/info)?
- Do state colors (hover, active, focus, disabled) form a system?

### Craft Details
- Are border-radii, shadows, and transitions consistent?
- Do micro-interactions (hover, focus, active) feel polished?
- Are edge cases handled (overflow, long text, missing images)?

**Scoring**: 90-100 = everything is part of one coherent system. 70-89 = mostly consistent with minor gaps. 50-69 = several inconsistencies. Below 50 = no system, ad-hoc choices throughout.

---

## Dimension 4: UX & Usability (20%, Subjective)

Scored against Nielsen's 10 heuristics + practical interaction checks.

### Nielsen's Heuristics (score each 0-10)
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

### Practical Checks
- Can a new user understand the page in 5 seconds?
- Are CTAs obvious and actionable?
- Do interactive elements look interactive (affordance)?
- Is navigation intuitive — can users find what they need?
- Are loading, empty, and error states present where needed?
- Do forms work correctly (submit, validation, feedback)?

**Scoring**: Nielsen total (0-100) averaged with practical assessment (0-100).

---

## Dimension 5: Aesthetic Fit (10%, Subjective)

Does the design match its purpose and audience?

- Is there a clear, committed aesthetic direction?
- Does every element serve that direction?
- Do typography, color, and layout create a unified mood?
- Is the intensity level appropriate? (a marketing page ≠ a dashboard)
- Does the design feel like it was made FOR this specific content?

**Scoring**: 90-100 = singular vision, every detail in service. 70-89 = clear direction with some generic elements. 50-69 = no clear direction, template feel. Below 50 = design and content feel disconnected.

---

## Dimension 6: Creative Distinction (15%, Subjective)

Does this avoid AI slop and have genuine personality?

### NEVER
- Generic fonts (Inter, Roboto, Arial, system-ui as primary)
- Purple gradients on white backgrounds
- Predictable centered card grids
- Cookie-cutter hero → features → pricing → footer
- Gratuitous rounded corners on everything
- Overuse of emoji as visual elements
- Same aesthetic as every other AI-generated landing page

### INSTEAD
- Distinctive typography that carries the design's voice
- Bold, committed color palettes (saturated, moody, or high-contrast)
- Layouts that surprise — asymmetry, overlap, grid-breaking
- Bespoke details that show intentional design decisions
- A personality someone would remember after closing the tab

**Scoring**: 90-100 = truly distinctive, couldn't be mistaken for template. 70-89 = has personality, mostly avoids AI patterns. 50-69 = looks like a template with some custom touches. Below 50 = indistinguishable from AI-generated default.

---

## Output Format

The subjective assessment (dimensions 3-6) must output:

```json
{
  "subjective_scores": {
    "visual_polish": 0,
    "ux_usability": 0,
    "aesthetic_fit": 0,
    "creative_distinction": 0
  },
  "nielsen_heuristics": {
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
  },
  "findings": [
    {
      "dimension": "visual_polish",
      "severity": "P1",
      "description": "Specific issue observed",
      "recommendation": "NEVER: [what to avoid]. INSTEAD: [what to do].",
      "impeccable_skill": "/typeset"
    }
  ],
  "links": [...],
  "hover_assessment": {...},
  "summary": "2-3 sentence assessment"
}
```

The orchestrator combines deterministic scores (performance, accessibility) with subjective scores to produce the overall.

## Calibration

- **50** = average website, passes basic checks
- **70** = good, professional quality, few issues
- **85+** = excellent, distinctive, production-ready
- Be honest. Most sites score 45-65.
