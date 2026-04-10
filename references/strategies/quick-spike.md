# Strategy: Quick Spike

Fast exploration for throwaway prototypes and proof-of-concepts.

## When to Use
- Validating an approach before committing to a full plan
- Time-boxed exploration (< 2 hours of work)
- The code may be thrown away

## Phases

### Context
enabled: true
guidance: "Limit to 3 most relevant files. No deep archaeology or vault search."

### Brainstorm
enabled: false

### Plan
enabled: true
guidance: "Single approach, no alternatives section. Skip external research. Use MINIMAL detail level."

### Work
enabled: true
guidance: "Prefer simplest working solution. Skip edge cases. Sequential mode only."

### Review
enabled: true
depth: shallow
guidance: "Security-sentinel and code-simplicity-reviewer only. Skip language-specific reviewers."

### Compound
enabled: false

### Docs
enabled: false
guidance: "Minimal dev log entry only. Skip ADRs."

## Pitfalls
- Spike code has a way of becoming production code. If you decide to keep it, re-run with full-process.
- Skipping review means security issues may slip through.
