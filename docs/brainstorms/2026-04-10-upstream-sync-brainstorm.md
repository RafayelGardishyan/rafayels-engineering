---
date: 2026-04-10
topic: upstream-sync-compound-engineering
---

# Upstream Sync: compound-engineering v2.59.0 → v2.62.1

## What We're Building

Selective sync of ~60 upstream commits (5 releases) from EveryInc/compound-engineering-plugin into our rafayels-engineering fork, plus two custom additions: an Obsidian vault researcher agent and pluggable orchestrator strategies.

The fork was created March 9, 2026 and hasn't been synced since. There is no git remote — changes are applied manually by reading upstream and adapting files.

## Scope — Include

### Security (Priority 1)
- **PR comment injection guard** (#490) — add untrusted-input warning to `pr-comment-resolver.md` and resolve-pr-feedback skill
- **Self-referencing example fix** (#496) — remove self-invocation examples from agents

### Token Optimizations (Priority 2)
- **ce:ideate + ce:review shortened** (#515) — core principles 7→3, cheapest-capable-model for sub-agents
- **ce:brainstorm Phase 3 to reference file** (#511) — ~120 lines moved to references/
- **ce:plan conditional references** (#489) — load references only when needed
- **document-review shortened** (#509) — lower cost per review

### Infrastructure (Priority 3)
- **Mandatory review in pipeline** (#433) — brainstorm runs document-review in Phase 3.5, plan runs it after confidence check
- **Stack-aware reviewer routing** (#497) — route reviewers based on tech stack in diff
- **Track-based learnings schema** (#445) — bug track vs knowledge track with different required fields
- **Learnings discoverability check** (#456) — verify docs/solutions/ files are findable

### New Features (Priority 4)
- **Universal planning** (#519) — non-software task support in plan/brainstorm workflows
- **Cross-invocation cluster analysis** (#480) — multi-round PR feedback pattern recognition
- **CLI agent-readiness reviewer** (#471) — checks CLI code for agent-friendliness
- **Product lens reviewer upgrade** (#481) — domain-agnostic, two-leg activation, strategic consequence analysis

### Custom Additions (Priority 5)
- **Obsidian vault researcher agent** — new agent using both obsidian-adr MCP (semantic search, graph traversal) AND obsidian MCP (general vault search). Searches ADRs, dev logs, meeting notes, and general vault content for organizational context during planning/brainstorm workflows. Modeled after the Slack researcher pattern but for Obsidian.
- **Pluggable orchestrator strategies** — 4 strategy files in `references/strategies/`:
  - `quick-spike.md` — skip brainstorm, lightweight plan, minimal review, no compound
  - `full-process.md` — full pipeline with deepening, swarm work, all reviewers, compound+ADR
  - `security-first.md` — mandatory security research, all security reviewers, compound mandatory
  - `review-only.md` — no brainstorm/plan/work, just multi-agent review + compound on existing code

## Scope — Exclude

- **Slack researcher** (#495) — we don't use Slack
- **Cross-platform model normalization** (#442) — not targeting Codex/Cursor
- **Context7 removal** (#486) — we still use Context7

## Why This Approach

Big-bang batch sync — apply all changes in one pass, grouped by file rather than by feature. This is faster to execute and avoids merge conflicts within files that would arise from incremental edits. One commit covers the full sync, with custom additions (vault researcher, orchestrator strategies) as separate follow-up commits for clarity.

## Key Decisions

- **Vault researcher scope**: Both ADR (obsidian-adr MCP) and general vault (obsidian MCP) — maximum discovery surface
- **Orchestrator design**: Separate strategy files (not mode parameters) — more modular, closer to upstream PR #502 vision
- **Strategy count**: 4 strategies (quick-spike, full-process, security-first, review-only) — covers the main workflow modes
- **Context7**: Keep it — still actively used in our plugin
- **No Slack**: Skip entirely — zero value without Slack MCP

## Open Questions

- How should /re:feature select a strategy? CLI arg, interactive prompt, or auto-detect?
- Should the vault researcher be dispatched conditionally (like Slack researcher) or always?
- Do we need a `docs/solutions/` directory structure for the learnings system?

## Next Steps

→ `/workflows:plan` for implementation details
