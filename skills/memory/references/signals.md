# Signal Types & Reward Formula

## Signal Types

| Type | Weight | When to emit | Range |
|---|---|---|---|
| `merge` | 0.40 | PR merged + CI passed | +1.0 merged, 0.5 merged but CI broken, 0.0 never merged |
| `approval` | 0.30 | User explicitly approved at phase handoff | +1.0 per approval, -0.3 per rework request |
| `review` | 0.20 | Code review outcome | +1.0 no findings, +0.5 P3 only, -0.3 P2, -1.0 P1 |
| `regression` | 0.10 | File touched by case was reverted OR new bug within 30d | -1.0 |

## Composite Reward Formula

```python
def composite_reward(signals: list[tuple[str, float]]) -> float:
    """Weighted mean of signals, mapped [-1,1] -> [0,1]. Neutral = 0.5."""
    if not signals:
        return 0.5
    by_type = group_by_type(signals)
    numerator = sum(WEIGHTS[t] * mean(values) for t, values in by_type.items())
    denominator = sum(WEIGHTS[t] for t in by_type)
    normalized = numerator / denominator  # [-1, 1]
    return clamp((normalized + 1.0) / 2.0, 0.0, 1.0)
```

Unsignaled cases stay at **0.5 (neutral)** — never default to success.

## Reward Decay at Retrieval

Older cases are trusted less. Applied at retrieval time, not storage:

```
effective_reward = stored_reward * exp(-age_days / 60)
```

- Half-life: ~42 days
- Exempt: cases with `status='promoted'`

## Quarantine Promotion

New cases start in `status='quarantine'` and are **not retrievable**.
They are promoted to `status='active'` by a SQL trigger when they accumulate
**2+ positive signals** (value > 0). This is the primary poisoning defense.

## Retrieval Cap

A case appearing in more than **30% of recent retrievals** (7-day window,
minimum 10 samples) is demoted in ranking. Prevents "sticky" cases from
dominating the bank.

## In-Process Signal Capture

Signals are emitted **during** workflows, not after. This way abandoned
workflows still produce useful partial signals:

| Workflow | Signals emitted |
|---|---|
| `/workflows:brainstorm` | `approval` (on user handoff) |
| `/workflows:plan` | `review` (from document-review) |
| `/workflows:work` | `ci` (tests pass/fail) |
| `/workflows:review` | `review` (severity-based) |
| `/re:feature` Phase 10 | `merge` (if PR merged) |
| `/workflows:compound` | `approval` (if promoted to critical patterns) |
