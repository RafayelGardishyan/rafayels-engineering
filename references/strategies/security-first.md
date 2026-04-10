# Strategy: Security First

Maximum security rigor for auth, payments, data handling, and privacy-sensitive features.

base: full-process

## When to Use
- Authentication, authorization, or session management
- Payment processing or financial data
- PII or sensitive data handling
- External API integrations with credentials
- Features with compliance requirements

## Phases

### Brainstorm
guidance: "Full brainstorm. Add threat modeling questions: What can go wrong? What's the attack surface? Who are the threat actors?"

### Plan
guidance: "Always run external research (security is high-risk). Mandatory security section in plan. A LOT detail level."

### Work
guidance: "Sequential mode only (no swarm — security code needs careful ordering). Tests required at every commit. Validate all inputs."

### Review
depth: thorough
guidance: "ALL agents, with special emphasis on: security-sentinel, data-integrity-guardian, agent-native-reviewer. Block on any security finding."

### Compound
guidance: "Mandatory. Document every security decision and its rationale."

### Docs
guidance: "Mandatory ADRs for ALL security decisions. Full dev log."

### Merge
guidance: "NO auto-merge. Require manual approval from a human reviewer."

## Pitfalls
- Sequential mode is slower but necessary — parallel execution can mask race conditions.
- Don't let thoroughness become paralysis. Ship when the security bar is met.
