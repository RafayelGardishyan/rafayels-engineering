# Universal Planning — Non-Software Tasks

This reference is loaded when a task is classified as non-software (travel, events, study plans, strategy docs, proposals).

## 5-Step Workflow

### Step 1: Ambiguity Assessment

Classify the task's complexity and domain:
- **Simple** (1-2 constraints): proceed directly to plan
- **Moderate** (3-5 constraints): run focused Q&A
- **Complex** (6+ constraints, multi-stakeholder): full brainstorm first

### Step 2: Focused Q&A (~3 questions)

Ask up to 3 targeted questions using AskUserQuestion:
1. **Scope**: What's the deliverable? (itinerary, schedule, proposal, checklist?)
2. **Constraints**: Budget, timeline, people involved?
3. **Success criteria**: How will you know this plan worked?

### Step 3: Quality Principles

Apply these principles (different from software):
1. **Completeness** — all logistics, dependencies, and stakeholders addressed
2. **Actionability** — every item is a concrete next step with an owner
3. **Time-boundness** — deadlines or timeframes on every phase
4. **Measurability** — success criteria defined (budget targets, attendance goals, completion checkpoints)
5. **Contingency** — fallback options for critical-path items

### Step 4: Output Format

Non-software plans use a different structure than software plans:

```markdown
---
title: "[Plan Title]"
type: [travel-plan | event-plan | study-plan | strategy | proposal]
date: YYYY-MM-DD
---

# [Plan Title]

## Objective
[What this plan achieves — 1-2 sentences]

## Timeline
| Phase | Dates | Actions | Owner |
|-------|-------|---------|-------|
| ... | ... | ... | ... |

## Checklist
- [ ] [Actionable item with deadline]
- [ ] [Actionable item with deadline]

## Resources
| Item | Budget | Status |
|------|--------|--------|
| ... | ... | ... |

## Decision Log
| Question | Deadline | Decision |
|----------|----------|----------|
| ... | ... | ... |

## Contingencies
- If [risk]: [fallback plan]
```

### Step 5: File Location & Handoff

Save to `docs/plans/YYYY-MM-DD-<type>-<topic>-plan.md` (same directory as software plans).
Present the plan and offer: "Plan ready. Review and refine, or done for now?"
