# Strategy: Review Only

Audit existing code or PRs without any implementation. For reviewing external contributions, inherited codebases, or post-hoc analysis.

## When to Use
- Reviewing a PR from an external contributor
- Auditing inherited or legacy code
- Post-incident code review
- Evaluating a dependency or library

## Phases

### Context
enabled: true
guidance: "Gather context about the code being reviewed. Check git history for recent changes."

### Brainstorm
enabled: false

### Plan
enabled: false

### Work
enabled: false

### Review
enabled: true
depth: thorough
guidance: "ALL agents via stack-aware routing. Present findings as actionable list."

### Compound
enabled: optional
guidance: "Offer to document findings. Useful for recording patterns found in audited code."

### Fix
guidance: "Present findings and offer to fix. Do not auto-fix — user decides."

### Merge
enabled: false
guidance: "Skip unless fixes were applied and user requests merge."

## Pitfalls
- Review without context can produce false positives. Always gather context first.
- Don't auto-fix findings — the user may disagree with the assessment.
