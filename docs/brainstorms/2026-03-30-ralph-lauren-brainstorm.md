---
date: 2026-03-30
topic: ralph-lauren-harness
---

# Ralph Lauren: Frontend Design Improvement Loop

## What We're Building

A Python harness that runs an autonomous frontend design improvement loop, inspired by Anthropic's GAN-like evaluator/generator pattern from their "Harness Design for Long-Running Apps" blog post.

The name: **Ralph Lauren** = Ralph Wiggum (loop/meme) + Designer Ralph Lauren.

## Architecture: 3-Component GAN Pattern

```
                    ┌─────────────────────┐
                    │   Python Harness     │
                    │  (Orchestrator)      │
                    └──────┬──────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
     ┌────────▼────────┐     ┌─────────▼─────────┐
     │   ASSESSOR       │     │   IMPROVER         │
     │  (Evaluator)     │     │  (Generator)       │
     │                  │     │                    │
     │  Deterministic:  │     │  Claude Agent SDK  │
     │  - Lighthouse    │     │  session with:     │
     │  - axe a11y      │     │  - Edit/Write/Bash │
     │  - CSS stats     │     │  - Assessment as   │
     │                  │     │    system context   │
     │  Subjective:     │     │  - Specific fix    │
     │  - Claude Agent  │     │    guidelines      │
     │    SDK session   │     │                    │
     │  - impeccable    │     │                    │
     │    .style rubric │     │                    │
     │  - agent-browser │     │                    │
     │    screenshots   │     │                    │
     └─────────────────┘     └────────────────────┘
```

## Key Design Decisions

### 1. Runtime: Claude Agent SDK (Python)
- `pip install claude-agent-sdk`
- Uses user's Claude Code subscription (no API key needed)
- `query()` function for one-shot sessions, `ClaudeSDKClient` for full control
- Each agent gets its own session with fresh context
- `permission_mode="acceptEdits"` for the improver (auto-accept file changes)
- `permission_mode="default"` for the assessor (read-only)

### 2. Assessor: Deterministic + Subjective (runs outside main session)

**Deterministic (pure Python, no Claude):**
- Lighthouse via `npx lighthouse --output=json` → performance, a11y, best practices scores
- axe-core via `npx axe` or Playwright integration → accessibility violations
- CSS stats via custom Python analysis → selector count, specificity, color count, font count

**Subjective (separate Claude Agent SDK session):**
- System prompt encodes impeccable.style rubric:
  - Nielsen's 10 heuristics scoring
  - Typography assessment (type scale, hierarchy, readability)
  - Spacing/layout assessment (consistency, rhythm, alignment)
  - Color assessment (harmony, contrast, palette coherence)
  - Craft assessment (polish, attention to detail)
  - Originality assessment (avoids generic AI aesthetics)
- Uses agent-browser via Bash tool to:
  - Navigate to the URL
  - Take full-page screenshots
  - Inspect interactive elements
  - Test UX flows
- Produces structured JSON assessment with scores + specific findings

### 3. Improver: Claude Agent SDK with full tools
- Gets the assessment report injected as the prompt
- System prompt focuses on design improvement methodology
- Has access to: Read, Write, Edit, Bash, Glob, Grep
- Works on the actual codebase to fix issues
- Commits changes incrementally

### 4. Loop Control: Max iterations + score threshold
- User specifies `--max-iterations N` (default: 5)
- User specifies `--target-score N` (default: 85/100)
- Loop exits when either: max iterations reached OR target score exceeded
- Each iteration's assessment + screenshot saved to `docs/ralph-lauren/`

### 5. Documentation: `docs/ralph-lauren/`
```
docs/ralph-lauren/
├── run-2026-03-30T14-30-00/
│   ├── iteration-1/
│   │   ├── screenshot-before.png
│   │   ├── screenshot-after.png
│   │   ├── assessment.json
│   │   └── changes.md
│   ├── iteration-2/
│   │   └── ...
│   └── summary.md          # Final report with score progression
```

## How It's Invoked

```bash
# Via Claude Code command
/re:ralph-lauren http://localhost:3000 --max-iterations 5 --target-score 85

# Or directly via Python
python skills/ralph-lauren/scripts/ralph_lauren.py \
  --url http://localhost:3000 \
  --cwd /path/to/project \
  --max-iterations 5 \
  --target-score 85
```

## What Gets Created

1. `commands/re/ralph-lauren.md` — The Claude Code command
2. `skills/ralph-lauren/SKILL.md` — Skill documentation
3. `skills/ralph-lauren/scripts/ralph_lauren.py` — Main harness orchestrator
4. `skills/ralph-lauren/scripts/assessor.py` — Assessment logic (deterministic + subjective)
5. `skills/ralph-lauren/scripts/improver.py` — Improvement session logic
6. `skills/ralph-lauren/scripts/metrics.py` — Deterministic metric collectors
7. `skills/ralph-lauren/references/assessment-rubric.md` — The impeccable.style-inspired rubric

## Resolved Questions

1. **Multiple URLs?** — No. One route at a time is sufficient.
2. **Previous iteration context?** — No. Each iteration gets a fresh context. Instead, design system choices are documented in `docs/ralph-lauren/philosophy.md` — a **page-agnostic design system** for the whole project that is referenced every iteration. The improver reads this file before making changes and updates it when making design system decisions (color palette, type scale, spacing rhythm, component patterns, etc.). This means the design system emerges organically and stays consistent across any page the loop runs on.

### philosophy.md Pattern
```
docs/ralph-lauren/
├── philosophy.md              # Persistent, page-agnostic design system
│                               # - Color palette & rationale
│                               # - Type scale & font choices
│                               # - Spacing rhythm & grid
│                               # - Component patterns
│                               # - Motion & interaction principles
│                               # Updated by improver, read by every iteration
├── run-2026-03-30T14-30-00/
│   ├── iteration-1/
│   │   ├── screenshot.png
│   │   ├── assessment.json
│   │   └── changes.md
│   └── summary.md
```

## Next Steps
→ `/workflows:plan` for implementation details
