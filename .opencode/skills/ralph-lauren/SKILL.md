---
name: ralph-lauren
description: "Frontend design improvement loop — autonomous evaluate-improve harness using Claude Agent SDK. Assesses pages with deterministic metrics (Lighthouse, axe, CSS) and subjective quality scoring (impeccable.style /audit + /critique methodology), then iteratively improves them. Triggers on 'improve design', 'design loop', 'ralph lauren', 'frontend quality'."
---

# Ralph Lauren: Frontend Design Improvement Loop

A Python harness that runs an autonomous evaluate-improve loop on frontend pages, inspired by Anthropic's GAN-like evaluator/generator pattern and impeccable.style's design assessment methodology.

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  DETERMINISTIC│     │  SUBJECTIVE  │     │  IMPROVER    │
│  METRICS      │     │  ASSESSOR    │     │  (Generator) │
│               │     │  (Evaluator) │     │              │
│  Lighthouse   │     │  /audit      │     │  /typeset    │
│  axe a11y     │────▶│  /critique   │────▶│  /arrange    │
│  CSS stats    │     │  agent-browser│     │  /colorize   │
│               │     │  6-dimension │     │  /normalize  │
│  (no LLM)     │     │  scoring     │     │  /polish ... │
└──────────────┘     └──────────────┘     └──────────────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  philosophy.md  │
                    │  (design system │
                    │   evolves here) │
                    └─────────────────┘
```

Each iteration:
1. **Collect deterministic metrics** — Lighthouse, axe, CSS stats (pure Python, no LLM)
2. **Run subjective assessment** — Separate Claude session using impeccable.style's `/audit` (5 technical dimensions) and `/critique` (Nielsen's 10 heuristics + persona testing) methodology, with agent-browser for visual inspection
3. **Run improvement session** — Separate Claude session that applies impeccable.style fix skills (`/typeset`, `/arrange`, `/colorize`, `/normalize`, `/polish`, etc.) to address findings
4. **Document** — Screenshots and assessments saved to `docs/ralph-lauren/`
5. **Update design system** — Improver updates `docs/ralph-lauren/philosophy.md` with any design system decisions (page-agnostic)
6. **Loop** — Context resets, next iteration starts fresh (only `philosophy.md` persists)

## Dependencies

```bash
# Required
pip install claude-agent-sdk anyio

# Required for screenshots/UX testing
npm install -g agent-browser

# Optional (deterministic metrics)
# Lighthouse and axe are invoked via npx — no global install needed
```

## Usage

### Via Claude Code command
```
/re:ralph-lauren http://localhost:3000
/re:ralph-lauren http://localhost:5173 --max-iterations 3 --target-score 90
```

### Via Python directly
```bash
python skills/ralph-lauren/scripts/ralph_lauren.py \
  --url http://localhost:3000 \
  --cwd /path/to/project \
  --max-iterations 5 \
  --target-score 85
```

### Standalone components
```bash
# Run only the subjective assessment
python skills/ralph-lauren/scripts/assessor.py --url http://localhost:3000

# Run only the improvement
python skills/ralph-lauren/scripts/improver.py \
  --url http://localhost:3000 \
  --assessment path/to/assessment.json
```

## Output Structure

```
docs/ralph-lauren/
├── philosophy.md                    # Persistent design system (page-agnostic)
├── run-2026-03-30T14-30-00/
│   ├── iteration-1/
│   │   ├── screenshot.png           # Pre-improvement screenshot
│   │   ├── screenshot-after.png     # Post-improvement screenshot
│   │   ├── assessment.json          # Full assessment with scores
│   │   ├── metrics.json             # Deterministic metrics
│   │   └── changes.md               # What the improver changed
│   ├── iteration-2/
│   │   └── ...
│   └── summary.md                   # Score progression table
```

## Assessment Methodology

### Deterministic (no LLM)
- **Lighthouse**: Performance, accessibility, best practices, SEO scores
- **axe-core**: Accessibility violations with impact ratings
- **CSS analysis**: Selector count, color count, font families, `!important` usage

### Subjective (Claude Agent SDK)
Uses impeccable.style methodology:

**Diagnostic phase:**
- `/audit`: Technical quality across 5 dimensions (normalize, harden, optimize, adapt, clarify)
- `/critique`: UX review via Nielsen's 10 heuristics, persona testing, cognitive load assessment

**Scoring dimensions (0-100 each):**
| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Heuristics | 20% | Nielsen's usability heuristics |
| Typography | 15% | Type scale, hierarchy, readability |
| Layout | 20% | Grid, spacing rhythm, alignment |
| Color | 15% | Palette, contrast, harmony |
| Craft | 15% | Polish, consistency, micro-interactions |
| Originality | 15% | Distinctiveness, avoids generic AI aesthetics |

### Improvement Skills Applied
Based on findings, the improver applies these impeccable.style skills:
- `/typeset` — typography fixes
- `/arrange` — layout and spacing
- `/colorize` — color system
- `/normalize` — design system alignment
- `/harden` — error handling and edge cases
- `/bolder` / `/quieter` — visual intensity
- `/distill` — simplification
- `/clarify` — UX copy
- `/polish` — final refinement
- `/delight` — personality and animation

## Design System Philosophy

The `philosophy.md` file is the key innovation — it's a page-agnostic design system that evolves organically across iterations. The improver reads it before making changes and updates it when making design system decisions. This means:

- Running the loop on `/dashboard` establishes colors, fonts, spacing
- Running it later on `/settings` reuses the same design system
- The system grows from specific decisions, not abstract planning
