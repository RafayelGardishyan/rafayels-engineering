---
date: 2026-04-24
type: feat
topic: re-feature-enforced-pipeline-extension
status: draft
---

# ✨ feat: Enforced `/re-feature` Pi workflow runtime

## Summary

Build a project-local Pi extension that turns Rafayel Engineering's current prompt-driven `/re:feature` workflow into a strict, extension-owned workflow runtime.

The new runtime will expose a canonical command:

```txt
/re-feature [feature description]
```

It will actively track the current workflow phase, inject phase-specific instructions, restrict tools and shell actions, validate phase completion through a fast subagent, and allow explicit user-approved bypasses when strict enforcement would otherwise block useful progress.

The existing `commands/re/feature.md` should remain as reference material initially. Once the extension is stable, that Markdown command can be changed into a thin pointer to `/re-feature` or an alias.

## Goals

- Make the feature workflow enforceable instead of relying on agent compliance.
- Track phase, strategy, optional source issue, artifacts, branch/worktree, PR, findings, bypasses, and history in session state.
- Inject the active phase prompt into the agent context on every turn.
- Restrict active tools and block out-of-phase tool calls.
- Require the agent to call a phase-advance tool instead of silently moving forward.
- Spawn a small validation subagent before advancing phases.
- Support explicit user bypass with an audit trail.
- Let us manually review and refine every phase prompt, tool list, and enforcement policy before finalizing.

## Non-goals for v1

- Fully replacing every existing workflow command such as `/workflows:brainstorm`, `/workflows:plan`, `/workflows:work`, `/workflows:review`, and `/workflows:compound`.
- Building a large custom TUI wizard before the state-machine behavior is proven.
- Supporting every possible alternate development workflow.
- Perfectly parsing arbitrary strategy Markdown forever. v1 can define typed strategy data in the extension and keep the Markdown files as human documentation.

## Key Pipeline Change

Review and compound should happen **before PR creation** to avoid wasting CI cycles.

Old flow:

```txt
implement → push branch → create PR → review/compound → address findings → merge
```

New enforced flow:

```txt
implement → local review → address findings if needed → local review until clean → compound → push branch → create PR → PR verification → merge
```

This means `git push`, `gh pr create`, and `gh pr merge` become phase-gated actions.

| Action | First allowed phase |
|---|---|
| `git push` | `push_branch` |
| `gh pr create` | `create_pr` |
| `gh pr merge` | `merge` |

## Proposed Phase List

Preflight: select strategy and optional source issue through a user-choice interface, then record the choice in workflow state.

Runtime phases:

1. `gather_context`
2. `clarify_feature`
3. `create_worktree`
4. `brainstorm`
5. `plan`
6. `implement`
7. `local_review`
8. `address_findings`
9. `compound`
10. `push_branch`
11. `create_pr`
12. `pr_verification`
13. `merge`
14. `update_docs`
15. `cleanup`
16. `summary`

## Architecture

Create a directory-style extension:

```txt
extensions/re-feature/
  index.ts
  phases.ts
  strategies.ts
  state.ts
  policies.ts
  validator.ts
  subagent.ts
  types.ts
```

`package.json` already loads `extensions/*.ts`; to load a directory extension, either:

1. add `extensions/re-feature/index.ts` explicitly to `package.json`'s `pi.extensions`, or
2. create a small `extensions/re-feature.ts` shim that imports and exports the directory implementation.

Recommended v1 approach: create `extensions/re-feature.ts` as a shim to avoid changing package loading semantics.

## Core Concepts

### Workflow state

Persist state using `pi.appendEntry()` and reconstruct from the current session branch on `session_start`.

```ts
interface ReFeatureState {
  active: boolean;
  workflowId: string;
  featureDescription: string;
  strategyId: string;
  phaseId: PhaseId;
  cwd: string;
  worktreePath?: string;
  branchName?: string;
  artifacts: {
    contextSummary?: string;
    brainstormDoc?: string;
    planDoc?: string;
    solutionDoc?: string;
    reviewFindingsPath?: string;
    prNumber?: string;
    prUrl?: string;
    devLogPath?: string;
    adrIds?: string[];
  };
  findings: Array<{
    id: string;
    severity: "p1" | "p2" | "p3";
    title: string;
    status: "open" | "fixed" | "deferred" | "accepted";
    sourcePhase: PhaseId;
  }>;
  bypasses: Array<{
    phaseId: PhaseId;
    kind: "advance" | "tool_call" | "policy";
    reason: string;
    approvedAt: number;
    approvedBy: "user";
    details?: unknown;
  }>;
  history: Array<{
    phaseId: PhaseId;
    enteredAt: number;
    exitedAt?: number;
    validator?: ValidatorResult;
    bypassed?: boolean;
  }>;
}
```

### Phase definition

Each phase is data-driven so its prompt/tools/properties can be reviewed manually.

```ts
interface PhaseDefinition {
  id: PhaseId;
  title: string;
  objective: string;
  prompt: string;
  tools: string[];
  allowedWriteGlobs: string[];
  blockedWriteGlobs?: string[];
  bashPolicy: BashPolicy;
  requiredArtifacts: ArtifactRequirement[];
  exitCriteria: string[];
  validatorPrompt: string;
  next?: PhaseId;
  skipWhen?: (state: ReFeatureState, strategy: StrategyDefinition) => boolean;
}
```

### Strategy definition

Strategies should become typed data in `strategies.ts`:

- `full-process`
- `quick-spike`
- `security-first`
- `review-only`

They can still mirror the existing files under `references/strategies/`, but runtime behavior should come from typed definitions.

```ts
interface StrategyDefinition {
  id: string;
  title: string;
  description: string;
  base?: string;
  strictness: "advisory" | "moderate" | "strict";
  phaseOverrides: Partial<Record<PhaseId, Partial<PhaseDefinition> & {
    enabled?: boolean | "optional";
  }>>;
}
```

Default strictness: **strict**, with explicit user bypass.

## Extension Commands

### `/re-feature [description]`

Starts the enforced workflow.

Behavior:

1. If `--issue=<id>` is provided, link the run to that open issue when found.
2. If no issue is provided and open `issue_tracker` issues exist, allow the user to select one or choose no source issue.
3. If description is missing and a source issue was selected, use the issue title as the feature description.
4. If description is still missing, ask the user for it.
5. Ask user to select a strategy unless `--strategy=<name>` is present.
6. Initialize workflow state.
7. Set session name to something like `re-feature: <short feature>`.
8. Enter the first enabled phase.
9. Send a user message telling the agent to begin the current phase.

### `/re-feature-status`

Shows current workflow state:

- phase
- strategy
- feature description
- expected artifacts
- allowed tools/actions
- last validator result
- bypass history

### `/re-feature-bypass`

User-facing manual bypass command.

Use cases:

- advance despite failed validator
- permit a blocked action once
- skip an optional phase

This command should always record an auditable bypass entry.

### `/re-feature-abort`

Stops enforcement for the current workflow after confirmation.

## Agent Tools

### `re_feature_status`

Read-only tool. Returns current phase, requirements, allowed actions, and missing known artifacts.

### `re_feature_advance_phase`

Agent-facing gate tool.

```ts
re_feature_advance_phase({
  evidence: string,
  requestedNextPhase?: PhaseId
})
```

Behavior:

1. Load current state.
2. Run validator subagent for the active phase.
3. If validator passes:
   - record validator result
   - transition to next enabled phase
   - persist state
   - update active tools
   - send/inject next phase instructions
4. If validator fails:
   - remain in current phase
   - return missing criteria and suggested fixes
5. If validator fails and UI is available:
   - optionally ask user whether to bypass, depending on policy.

### `re_feature_request_bypass`

Agent-facing bypass request.

```ts
re_feature_request_bypass({
  reason: string,
  kind: "advance" | "tool_call" | "policy",
  details?: unknown
})
```

It asks the user for explicit approval and records the result.

## Context Injection

Use `before_agent_start` while a workflow is active.

Injected message should include:

- workflow name
- current phase
- selected strategy
- linked source issue, if any
- phase objective
- allowed tools/actions
- blocked actions
- expected artifacts
- exit criteria
- instruction to call `re_feature_advance_phase` when ready
- reminder that bypass must be explicit and user-approved

Example shape:

```md
[RE-FEATURE ENFORCED WORKFLOW ACTIVE]

Current phase: plan
Strategy: full-process

Objective:
Create a detailed implementation plan from the approved brainstorm.

Strict enforcement:
- Do not edit production code in this phase.
- Only write to docs/plans/**.
- Do not run git push, gh pr create, or gh pr merge.

Exit criteria:
- Plan document exists under docs/plans/.
- Plan references the brainstorm document.
- Testing strategy is included.
- User has approved moving to implementation.

When complete, call re_feature_advance_phase with evidence.
```

## Tool Enforcement

Use both `pi.setActiveTools()` and `tool_call` blocking.

### Active tools

Each phase supplies a tool list. The extension sets active tools on phase entry.

Must include extension/always-available workflow tools during active workflow:

- `re_feature_status`
- `re_feature_record_artifact`
- `re_feature_advance_phase`
- `re_feature_request_bypass`

ADR access should also be available in every phase. If project config sets `adr.location=repo`, use repo ADR files via `re_feature_adr` instead of ADR MCP tools. Otherwise use ADR plugin tools when loaded:

- `re_feature_adr`
- `semantic_search`
- `get_adr`
- `query_graph`
- `list_adrs`
- `list_connections`

### Write restrictions

For `edit` / `write`, enforce `allowedWriteGlobs`. Some phases intentionally do not expose general write/edit at all and instead require controlled proxy tools.

Examples:

- ADR routing: `re_feature_adr` checks `adr.location`; when set to `repo`, search/list/get ADR markdown files from `adr.repo_dir` rather than using ADR MCP tools.
- `gather_context`: no writes
- `brainstorm`: no general write/edit; create/update `docs/brainstorms/**` only through `re_feature_record_artifact`
- `plan`: no general write/edit; create/update `docs/plans/**` only through `re_feature_record_artifact`
- `compound`: preferably create `docs/solutions/**` through `re_feature_record_artifact`; general writes can be reviewed later
- issue management: use `issue_tracker`, never direct `.pi/issues/**` writes
- `update_docs`: docs/dev-log/ADR locations

### Bash restrictions

Block or require bypass for shell commands.

Globally block without bypass:

- obvious destructive commands such as `rm -rf /`, `sudo rm`, filesystem wipes
- credential exfiltration patterns

Phase-gated commands:

- block `git push` before `push_branch`
- block `gh pr create` before `create_pr`
- block `gh pr merge` before `merge`
- block `git checkout`, `git switch`, worktree mutation outside `create_worktree` unless allowed
- block package installation outside implementation unless user bypasses

## Validator Subagent

Implement in `validator.ts` / `subagent.ts` by spawning a fresh Pi process in JSON mode, similar to Pi's subagent extension pattern.

Suggested invocation:

```bash
pi --mode json -p --no-session \
  --tools read,bash \
  --append-system-prompt <tmp-validator-system-prompt> \
  "<validator task>"
```

Use a fast model if configurable. Add an extension-level constant or setting for validator model.

Validator output must be strict JSON:

```json
{
  "pass": true,
  "confidence": "high",
  "missing": [],
  "artifacts": {
    "planDoc": "docs/plans/..."
  },
  "notes": "..."
}
```

Malformed output should fail closed:

```ts
pass = false;
missing = ["Validator returned malformed output"];
```

Validator must be skeptical and should inspect filesystem/git state, not just trust agent evidence.

## Phase Review Loop

Because phase prompts and policies need manual review, implementation should not finalize all phase definitions in one pass.

Use this staged process:

1. Implement extension skeleton and generic state machine.
2. Add placeholder phase definitions.
3. Review and finalize phases one by one with the user:
   - objective
   - injected prompt
   - active tools
   - write policy
   - bash policy
   - required artifacts
   - exit criteria
   - validator prompt
4. Only after approval, wire strict enforcement for that phase.

Recommended review order:

Preflight choice recording, then:

1. `gather_context`
2. `clarify_feature`
3. `create_worktree`
4. `brainstorm`
5. `plan`
6. `implement`
7. `local_review`
8. `address_findings`
9. `compound`
10. `push_branch`
11. `create_pr`
12. `pr_verification`
13. `merge`
14. `update_docs`
15. `cleanup`
16. `summary`

## Initial Phase Policy Sketches

These are draft sketches only; each must be reviewed before implementation is considered final.

### Preflight: strategy and source issue selection

- UI: use an ask-user-question-like selection flow.
- Options: select strategy, select open source issue or explicitly choose none.
- Writes: none.
- Recording: persist `preflight.selectedAt`, `preflight.strategyId`, `preflight.strategyLabel`, and optional `preflight.sourceIssue` in workflow state.
- Runtime: not an active phase; enforcement starts at `gather_context`.

### `gather_context`

- Tools: `read`, `bash`, `issue_tracker`, and ADR plugin tools when available (`semantic_search`, `get_adr`, `query_graph`, `list_adrs`, `list_connections`).
- Writes: none.
- Bash: allow read-only commands (`ls`, `find`, `rg`, `git status`, `git log`).
- Required context sources: selected source issue if any, README/docs, relevant commands/workflows, relevant extensions/skills patterns, related open issues, ADR plugin research, and dev-log context when available.
- Exit: context summary recorded with constraints, patterns, relevant ADR decisions or ADR-unavailable note, blockers, and open questions.

### `clarify_feature`

- Tools: `ask_user_question`, `read`, `bash` read-only, `issue_tracker`, and ADR plugin tools when available (`semantic_search`, `get_adr`, `query_graph`, `list_adrs`, `list_connections`).
- Writes: none.
- Rules: ask targeted questions one at a time; prefer multiple choice; do not brainstorm or plan yet.
- ADR use: if clarification reveals a new architectural area, use ADR plugin research before finalizing the clarified definition, or explicitly record that ADR tools are unnecessary/unavailable.
- Exit: feature goal/problem, expected outcome, success criteria, constraints, non-goals, and open questions are clear; user confirms the clarified feature definition.

### `create_worktree`

- Tools: `bash`, `read`.
- Behavior: fully automated in the normal path; do not ask the user to choose a worktree strategy.
- Writes: git worktree/branch metadata only.
- Bash: allow `pwd`, `ls`, `git status`, `git branch`, `git symbolic-ref`, `git rev-parse`, `git pull`, and `git worktree`; block commit/push/PR/merge.
- Automation: detect default branch, pull it, derive a meaningful branch name from the feature or linked issue, and create an isolated worktree for that branch.
- Bypass: only request user bypass if automation is impossible or unsafe, for example dirty default-branch state blocks worktree creation.
- Exit: base branch, created branch, and worktree path recorded; no implementation edits, commits, push, PR, or merge occurred.

### `brainstorm`

- Tools: `read`, `bash` read-only, `ask_user_question`, `issue_tracker`, workflow lifecycle tools, and ADR plugin tools. No general `write`/`edit` tools.
- Writes: no direct file writes; create/update `docs/brainstorms/**` only through `re_feature_record_artifact` as a controlled artifact proxy.
- Issue management: use `issue_tracker`, never direct `.pi/issues/**` writes.
- Rules: do not write implementation code; do not create the implementation plan yet; ask design questions one at a time with `ask_user_question`; prefer multiple choice; consider 2–3 approaches unless strategy disables alternatives; apply YAGNI.
- Artifact management: create/update and record the brainstorm document with `re_feature_record_artifact({ key: "brainstormDoc", value: { path: "docs/brainstorms/...", content: "..." } })`.
- Exit: brainstorm doc exists under `docs/brainstorms/**`, includes summary/context/approaches/recommendation/key decisions/open questions/next step, incorporates linked issue/context/ADR constraints where relevant, and user approved proceeding to planning.

### `plan`

- Tools: `read`, `bash` read-only, `ask_user_question`, `issue_tracker`, workflow lifecycle tools, and ADR plugin tools. No general `write`/`edit` tools.
- Writes: no direct file writes; create/update `docs/plans/**` only through `re_feature_record_artifact` as a controlled artifact proxy.
- Issue management: use `issue_tracker`, never direct `.pi/issues/**` writes.
- Rules: do not implement code; do not edit production files; include dependency-ordered tasks, acceptance criteria, testing strategy, local review + compound-before-PR strategy, artifact recording points, open questions, and ADR implications.
- Artifact management: create/update and record the plan document with `re_feature_record_artifact({ key: "planDoc", value: { path: "docs/plans/...", content: "..." } })`.
- Exit: plan doc exists, references brainstorm where applicable, includes testing strategy and review/compound-before-PR strategy, artifact path is recorded, and user approved implementation.

### `implement`

- Tools: `read`, `bash`, `edit`, `write`, `issue_tracker`, `subagent`/Codex if available, workflow lifecycle tools, and ADR plugin tools.
- Writes: code/tests/docs needed for implementation, but restricted to the recorded `worktreePath` once available. Direct writes to `.pi/issues/**`, `.git/**`, `node_modules/**`, and `.env*` are blocked.
- Package installation: open/allowed during implementation when needed.
- Issue management: use `issue_tracker`, never direct `.pi/issues/**` writes.
- ADR use: use ADR plugin tools when implementation touches architectural decisions; record new decisions for `update_docs`/ADR phase.
- Artifact management: record `implementationSummary` and `testsRun` with `re_feature_record_artifact` before advancing.
- Block: `git push`, `gh pr create`, `gh pr merge`.
- Exit: implementation complete or explicitly deferred, relevant tests run and summarized, issue tracker updated, local commits created for complete logical units or uncommitted state justified.

### `local_review`

- Tools: `read`, `bash`, review subagents, `issue_tracker`, workflow lifecycle tools, and ADR plugin tools.
- Writes: no direct file writes; create/update review findings artifact only through `re_feature_record_artifact({ key: "reviewFindingsPath", value: { path, content } })`.
- Issue management: capture all actionable findings through `issue_tracker`, never direct `.pi/issues/**` writes.
- Loop behavior: if open actionable/blocking findings exist, phase advancement goes to `address_findings` instead of proceeding to `compound`.
- Block: implementation fixes, production edits, push, PR create, merge.
- Exit: review run according to strategy, findings captured/triaged, and only non-actionable/accepted/deferred findings remain before proceeding.

### `address_findings`

- Role: proxy for `implement`, scoped specifically to local review findings and positioned before `compound`.
- Tools: `read`, `bash`, `edit`, `write`, `issue_tracker`, `subagent`/Codex if available, workflow lifecycle tools, and ADR plugin tools.
- Writes: code/tests/docs needed for finding fixes, restricted to recorded `worktreePath`; direct writes to `.pi/issues/**`, `.git/**`, `node_modules/**`, and `.env*` are blocked.
- Package installation: open/allowed when needed for fixes.
- Issue management: close fixed findings immediately through `issue_tracker`; defer/accept only with explicit user approval.
- Flow: after addressing findings, normally return to `local_review` for verification; proceed to `compound` only once review is clean or remaining findings are accepted/deferred.
- Artifact management: update `implementationSummary` and `testsRun` with `re_feature_record_artifact` before advancing.
- Block: `git push`, `gh pr create`, `gh pr merge`.
- Exit: P1 fixed, P2 fixed or explicitly accepted/deferred, tests rerun and summarized, issue tracker synchronized, local fix commits created or uncommitted state justified.

### `compound`

- Tools: `read`, `bash` read-only, `memory_write`, `issue_tracker`, workflow lifecycle tools, and ADR plugin tools. No general `write`/`edit` tools.
- Writes: no direct file writes; create/update `docs/solutions/**` only through `re_feature_record_artifact` as a controlled artifact proxy.
- Artifact management: create/update and record the solution document with `re_feature_record_artifact({ key: "solutionDoc", value: { path: "docs/solutions/...", content: "..." } })`.
- Exit: solution/memory artifact exists unless strategy skips compound; review findings, implementation lessons, reusable patterns, and ADR follow-up needs captured.

### `push_branch`

- Tools: `bash`, `read`, workflow lifecycle tools, and ADR plugin tools.
- Writes: none.
- Bash: allow `pwd`, `git status`, `git branch`, `git log`, `git diff`, `git remote`, `git rev-parse`, and `git push`.
- Block: file edits, `gh pr create`, `gh pr merge`, `git push --force` / `-f`, and `git push --no-verify`.
- Rules: only push the recorded branch from the recorded worktree; verify branch/worktree/remote before pushing; stop rather than force-push on remote conflicts.
- Artifact management: record `pushSummary` with `re_feature_record_artifact` after push.
- Exit: branch pushed, upstream tracking set, push summary recorded, no PR created, no merge performed.

### `create_pr`

- Tools: `bash`, `read`, workflow lifecycle tools, and ADR plugin tools.
- Bash: allow `gh pr create`, `gh pr view`, plus read-only git status/log/diff/branch/rev-parse.
- Block: edits/writes and `gh pr merge`.
- Artifact management: record `prUrl`, `prNumber` when known, and `prSummary` with `re_feature_record_artifact`.
- Exit: PR number/URL recorded and PR body contains summary/testing/context/artifact links plus local-review/compound-before-PR note.

### `pr_verification`

- Tools: `bash`, `read`, workflow lifecycle tools, and ADR plugin tools.
- Bash: allow `gh pr checks`, `gh pr view`, `gh run list`, `gh run watch`, and read-only git status/log/diff.
- Edits: none; failed verification transitions back to `address_findings`.
- Artifact management: record `prVerificationSummary` with `re_feature_record_artifact`.
- Exit: CI/check status known; green checks or user-approved bypass before merge.

### `merge`

- Tools: `bash`, `read`, `ask_user_question`, workflow lifecycle tools, and ADR plugin tools.
- Bash: allow `gh pr merge`, `gh pr view`, `gh pr checks` only.
- Security-first: require manual human approval; no automerge by default.
- Artifact management: record `mergeSummary` with `re_feature_record_artifact`.
- Exit: merge/automerge status recorded and security-first approval honored.

### `update_docs`

- Tools: `read`, `bash`, `write`, `edit`, `memory_write`, `issue_tracker`, workflow lifecycle tools, and ADR plugin tools.
- Writes: documentation/reference paths only (`docs/**`, `README.md`, `commands/**`, `references/**`); issue updates through `issue_tracker` only.
- ADR use: create/update ADRs for architectural decisions when applicable.
- Artifact management: record `docsSummary` with `re_feature_record_artifact`.
- Exit: required documentation/dev-log/ADR updates complete; no implementation code changed.

### `cleanup`

- Tools: `bash`, `read`, workflow lifecycle tools, and ADR plugin tools.
- Bash: allow safe `git status`, `git worktree`, and `git branch` commands.
- Writes: no file edits.
- Artifact management: record `cleanupSummary` with `re_feature_record_artifact`.
- Exit: worktree cleaned or intentionally retained.

### `summary`

- Tools: mostly read-only plus workflow lifecycle tools and ADR plugin tools.
- Writes: none.
- Exit: final user-facing summary emitted with feature/source issue, strategy, branch/worktree, artifacts, implementation/tests, review status, PR/merge, docs/ADR/memory updates, cleanup, and bypasses.

## Testing Plan

### Manual smoke tests

1. Start `/re-feature "test workflow enforcement"`.
2. Verify status footer/widget appears.
3. Try to edit production code during `gather_context`; expect block.
4. Try `git push` before `push_branch`; expect block.
5. Try advancing without required artifacts; expect validator failure.
6. Approve a user bypass; verify it is recorded.
7. Reload Pi; verify workflow state restores.
8. Continue to next phase; verify tools and injected prompt update.

### Automated/lightweight tests where possible

- Unit-test pure policy helpers:
  - phase resolution
  - strategy overlay
  - glob matching
  - bash command classification
  - next-phase skipping
  - validator JSON parsing
- Add a local test script if repo conventions support it.

## Implementation Steps

- [x] Create extension skeleton files.
- [x] Define shared types in `types.ts`.
- [x] Implement state reconstruction/persistence in `state.ts`.
- [x] Implement command registration in `index.ts`.
- [x] Treat strategy/source-issue selection as preflight state instead of a runtime phase.
- [x] Allow `/re-feature` runs to select/link an open issue from `.pi/issues` / `issue_tracker` storage.
- [x] Implement context injection and status UI.
- [x] Implement `re_feature_status`.
- [x] Implement `re_feature_record_artifact` artifact/state recording.
- [x] Implement `re_feature_advance_phase` with validator integration.
- [x] Implement bypass command/tool and audit logging.
- [x] Implement policy helpers and tool-call blocking.
- [x] Implement subagent validator runner.
- [x] Add typed strategies.
- [x] Add placeholder phase definitions.
- [ ] Review phase definitions with the user one by one.
- [ ] Finalize strict policies per approved phase.
- [ ] Run smoke tests.
- [ ] Update `commands/re/feature.md` to reference `/re-feature` once stable.

## Risks and Mitigations

### Risk: strict enforcement blocks legitimate work

Mitigation: explicit user bypass with audit trail and clear missing criteria.

### Risk: validator subagent is slow

Mitigation: use read-only tools, short prompts, and a configurable fast model.

### Risk: phase policies become too complex

Mitigation: keep phases data-driven and review them individually.

### Risk: command collision with `/re:feature`

Mitigation: ship `/re-feature` first. Change/alias `/re:feature` later.

### Risk: strategy Markdown and typed strategy data drift

Mitigation: either generate docs from typed strategies later or add a note that typed strategy definitions are runtime source of truth.

## Open Questions

1. Which fast model should the validator subagent use by default?
2. Should bypass approval be allowed from the agent tool flow, or only from explicit user command?
3. Should phase definitions live only in TypeScript, or in separate JSON/Markdown files for easier review?
4. Should the extension create `.pi/re-feature/` artifacts, or keep all persistent workflow data in the Pi session only?
5. Should `local_review` findings use the existing `issue_tracker` tool by default?

## Recommendation

Proceed with the extension skeleton first, then pause for manual phase-spec review before locking in strict enforcement. The first implementation milestone should prove:

- `/re-feature` starts a tracked workflow
- current phase is injected into context
- status is visible
- phase advance runs a validator stub
- out-of-phase `git push` / `gh pr create` / `gh pr merge` are blocked
- user bypass is recorded

After that, fill in and approve the real phase definitions one by one.
