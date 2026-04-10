# Strategy: Full Process

Complete pipeline for production features. Maximum rigor and documentation.

## When to Use
- Production features that will be maintained long-term
- Features touching multiple systems or services
- Default strategy when none is specified

## Phases

### Context
enabled: true
guidance: "Full context gathering. Include vault researcher if Obsidian MCP is available."

### Brainstorm
enabled: true
guidance: "Full brainstorm with document-review in Phase 3.5. Wait for user approval."

### Plan
enabled: true
guidance: "Full research (local + external). A LOT detail level. Run deepen-plan after creation."

### Work
enabled: true
guidance: "Swarm mode for 5+ independent tasks. Sequential otherwise. Tests required."

### Review
enabled: true
depth: thorough
guidance: "ALL agents via stack-aware routing. No filtering."

### Compound
enabled: true
guidance: "Mandatory. Create full solution doc in docs/solutions/."

### Docs
enabled: true
guidance: "Mandatory ADRs for architectural decisions. Full dev log. Update project docs."

## Pitfalls
- Can be slow for small changes. Use quick-spike for exploration.
- Swarm mode on small tasks creates coordination overhead.
