---
date: 2026-03-30
topic: ralph-lauren-v2-assessment-rewrite
---

# Ralph Lauren v2: Research-Backed Assessment Rewrite

## What We're Building

Rewrite the assessment layer of the ralph-lauren harness from the bottom up, replacing ad-hoc scoring with research-backed criteria from three sources:
1. Frontend performance metrics (Core Web Vitals, architectural metrics)
2. Accessibility essentials (concrete DOM-checkable rules)
3. Improving Claude's frontend output (evaluation criteria, NEVER/INSTEAD prompts)

## Architecture: Three-Layer Assessment Stack

```
Layer 1: DETERMINISTIC (Python, no LLM)
├── Core Web Vitals via web-vitals JS injection (LCP, CLS, INP, FCP, TBT)
├── CSS statistics (colors, fonts, specificity, units analysis)
├── Lighthouse scores (supplementary, not primary)
└── Results: structured JSON with pass/fail thresholds

Layer 2: STRUCTURAL (DOM analysis via agent-browser, no LLM)
├── Semantic HTML audit (<div onClick> vs <button>, <form> patterns)
├── 15-point accessibility checklist from article 2
├── DOM segmentation maps (existing approach)
└── Results: structured JSON with pass/fail per check

Layer 3: SUBJECTIVE (Claude session, informed by layers 1+2)
├── 5 criteria from article 3 evaluation methodology
├── Impeccable.style /audit + /critique (kept)
├── Hover + link testing (kept)
└── NEVER/INSTEAD structured recommendations
```

## Scoring: 6 Research-Backed Dimensions

| Dimension | Source | Weight | What it measures |
|-----------|--------|--------|-----------------|
| Performance | Layer 1 | 15% | Core Web Vitals thresholds |
| Accessibility | Layer 1+2 | 20% | Concrete a11y checks |
| Visual Polish & Coherence | Layer 3 | 20% | Typography, spacing, color system consistency |
| UX & Usability | Layer 3 | 20% | Nielsen heuristics, interaction quality |
| Aesthetic Fit | Layer 3 | 10% | Does the design match its purpose/audience |
| Creative Distinction | Layer 3 | 15% | Avoids AI slop, has personality |

## Key Decisions

- **Layer 2 is new**: concrete a11y checks move OUT of LLM into deterministic code
- **CWV collected via JS injection**: not just Lighthouse scores — actual PerformanceObserver data
- **Subjective scoring uses article 3's 5 criteria**: proven via 50-prompt evaluation
- **Improver prompts use NEVER/INSTEAD structure**: per article 3 findings
- **Smaller scope per iteration**: assessor gets pre-computed results, focuses on design quality

## Next Steps
→ Plan implementation details
