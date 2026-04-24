import type { PhaseDefinition, PhaseId } from "./types.js";

const adrTools = ["re_feature_adr", "semantic_search", "get_adr", "query_graph", "list_adrs", "list_connections"];
const lifecycleTools = ["re_feature_status", "re_feature_record_artifact", "re_feature_advance_phase", "re_feature_request_bypass", ...adrTools];
const readOnlyBash = {
  readOnly: true,
  allowedPatterns: [
    "^\\s*(pwd|ls|find|rg|grep|cat|head|tail|wc)(\\s|$)",
    "^\\s*git\\s+(status|log|show|diff|branch)(\\s|$)",
    "^\\s*gh\\s+(issue|pr)\\s+(list|view)(\\s|$)",
  ],
};

function phase(def: Omit<PhaseDefinition, "prompt" | "validatorPrompt"> & Partial<Pick<PhaseDefinition, "prompt" | "validatorPrompt">>): PhaseDefinition {
  return {
    ...def,
    blockedWriteGlobs: [".pi/issues/**", ...(def.blockedWriteGlobs ?? [])],
    prompt:
      def.prompt ??
      `You are in the enforced /re-feature phase: ${def.title}.\n\nObjective:\n${def.objective}\n\nStay within this phase. When complete, call re_feature_advance_phase with concrete evidence.`,
    validatorPrompt:
      def.validatorPrompt ??
      `Validate whether phase ${def.id} (${def.title}) is complete. Be skeptical. Check filesystem/git state when relevant. Return strict JSON with pass, confidence, missing, artifacts, and notes.`,
  };
}

export const PHASE_ORDER: PhaseId[] = [
  "gather_context",
  "clarify_feature",
  "create_worktree",
  "brainstorm",
  "plan",
  "implement",
  "local_review",
  "address_findings",
  "compound",
  "push_branch",
  "create_pr",
  "pr_verification",
  "merge",
  "update_docs",
  "cleanup",
  "summary",
];

export const PHASES: Record<PhaseId, PhaseDefinition> = {
  select_strategy: phase({
    id: "select_strategy",
    title: "Select Strategy (Preflight)",
    objective: "Preflight-only pseudo-phase: select strategy and optional source issue before entering the enforced runtime.",
    prompt: "This is not an active runtime phase. /re-feature records the strategy and optional source issue during command preflight, then starts enforcement at gather_context.",
    tools: lifecycleTools,
    allowedWriteGlobs: [],
    bashPolicy: { readOnly: true },
    requiredArtifacts: [],
    exitCriteria: ["Strategy selected and recorded", "Source issue selected or explicitly skipped"],
  }),
  gather_context: phase({
    id: "gather_context",
    title: "Gather Project Context",
    objective: "Research relevant project docs, ADRs, recent work, and constraints before feature design.",
    prompt: `You are in Phase: gather_context.

Objective:
Research relevant project documentation, the selected source issue if any, existing workflow files, current issue context, Architecture Decision Records through the ADR plugin when available, dev logs when available, and nearby implementation patterns before clarifying or designing the feature.

Strict rules:
- Do not brainstorm solutions yet.
- Do not create implementation plans yet.
- Do not edit files.
- First call re_feature_adr repo_status to determine whether project config says ADRs are in repo.
- If adr.location=repo, use re_feature_adr search/list/get against repo ADR files instead of ADR MCP tools.
- Otherwise use the ADR plugin tools for semantic ADR search/reading/graph traversal when they are available.
- If ADR tools are unavailable, explicitly record that ADR research was unavailable.

Required context sources:
- Selected source issue, if any
- README.md and relevant docs/
- Existing commands/workflows related to the feature
- Existing extensions/ or skills/ patterns if the feature touches Pi extensions
- Open issue_tracker items that may affect this work
- ADR research: repo ADR files via re_feature_adr when adr.location=repo, otherwise ADR plugin semantic search/read/graph traversal when available
- Dev-log context when available

When complete, summarize:
- Relevant architectural constraints
- Existing patterns to follow
- Relevant ADR decisions or that ADR research was unavailable
- Blockers/dependencies/open questions

Then call re_feature_advance_phase with concrete evidence.`,
    tools: ["read", "bash", "issue_tracker", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [{ key: "contextSummary", description: "Synthesized project context summary", required: true }],
    exitCriteria: [
      "Selected source issue, if any, has been read and incorporated",
      "Relevant README/docs/commands/extensions files scanned",
      "Existing implementation patterns identified",
      "ADR research completed through repo ADR files when adr.location=repo, otherwise through ADR plugin semantic search/read/graph traversal, or explicitly unavailable",
      "Related open issues checked",
      "Context summary includes constraints, patterns, blockers, and open questions",
      "No files modified",
    ],
  }),
  clarify_feature: phase({
    id: "clarify_feature",
    title: "Clarify Feature",
    objective: "Ensure the feature request and success criteria are clear before design work begins.",
    prompt: `You are in Phase: clarify_feature.

Objective:
Turn the initial feature description, linked source issue if any, gathered context, and user input into a clear feature definition before brainstorming.

Strict rules:
- Do not brainstorm solution approaches yet.
- Do not create implementation plans yet.
- Do not edit files.
- Ask targeted questions one at a time.
- Prefer multiple-choice questions when natural options exist.
- If clarification reveals a new architectural area, use ADR plugin tools to check relevant decisions before finalizing the clarified definition.

Clarify and record:
- User-facing problem or goal
- Expected outcome
- Success criteria
- Constraints
- Non-goals
- Open questions, if any

When complete, restate the clarified feature definition and ask the user to confirm it. Then call re_feature_advance_phase with concrete evidence.`,
    tools: ["read", "bash", "ask_user_question", "issue_tracker", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [],
    exitCriteria: [
      "Initial feature description/source issue has been restated accurately",
      "User-facing problem or goal is clear",
      "Success criteria are explicit",
      "Important constraints and non-goals are recorded",
      "Ambiguities are resolved or listed as open questions",
      "ADR plugin research was used if clarification revealed a new architectural area, or explicitly unnecessary/unavailable",
      "User confirmed the clarified feature definition",
      "No files modified",
    ],
  }),
  create_worktree: phase({
    id: "create_worktree",
    title: "Create Worktree",
    objective: "Automatically create an isolated worktree/branch for the feature.",
    prompt: `You are in Phase: create_worktree.

Objective:
Automatically create an isolated Git worktree/branch for this feature. All subsequent feature work must happen in that worktree.

Strict rules:
- Do not ask the user to choose a worktree strategy in the normal path.
- Do not edit feature files yet.
- Do not implement anything yet.
- Do not commit, push, create a PR, or merge.
- Prefer deterministic automation: detect the default branch, pull it, create a meaningful branch name from the feature or linked issue, and create a worktree for that branch.
- Only request a bypass if automation is impossible or unsafe, for example dirty default branch state blocks worktree creation.

When complete, record in evidence:
- current starting directory
- default/base branch
- created branch name
- created worktree path
- confirmation that no push/PR/merge occurred

Then call re_feature_advance_phase with concrete evidence.`,
    tools: ["read", "bash", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: {
      allowedPatterns: [
        "^\\s*pwd\\s*$",
        "^\\s*ls(\\s|$)",
        "^\\s*git\\s+(status|branch|symbolic-ref|rev-parse|pull|worktree)(\\s|$)",
      ],
    },
    requiredArtifacts: [],
    exitCriteria: [
      "Default/base branch checked",
      "Meaningful feature branch created from the feature or linked issue",
      "Isolated worktree created automatically",
      "Worktree path recorded in evidence",
      "Branch name recorded in evidence",
      "No implementation edits made",
      "No commit/push/PR/merge performed",
    ],
  }),
  brainstorm: phase({
    id: "brainstorm",
    title: "Brainstorm",
    objective: "Explore requirements and approaches; create an approved brainstorm document.",
    prompt: `You are in Phase: brainstorm.

Objective:
Explore requirements and high-level approaches for the clarified feature before implementation planning.

Inputs:
- Linked source issue, if any
- Gathered context summary
- Clarified feature definition
- Relevant ADR findings and constraints

Strict rules:
- Do not write implementation code.
- Do not create the implementation plan yet.
- Do not use general write/edit tools; create or update the brainstorm document only through re_feature_record_artifact.
- Do not write issue JSON files directly; use issue_tracker for issue management.
- Ask the user clarifying/design questions one at a time with ask_user_question.
- Prefer multiple-choice questions when natural options exist.
- Consider 2–3 approaches with tradeoffs unless the strategy explicitly disables alternatives.
- Apply YAGNI: choose the simplest approach that solves the stated problem.
- Use re_feature_adr when adr.location=repo, otherwise ADR plugin tools, whenever brainstorming touches architectural decisions or prior constraints.
- Create/update and record the brainstorm document through re_feature_record_artifact using key brainstormDoc as soon as it exists.

Required brainstorm document:
docs/brainstorms/YYYY-MM-DD-<topic>-brainstorm.md

Document must include:
- What we're building
- Why
- Context/constraints
- Approaches considered
- Recommendation
- Key decisions
- Open questions
- Next step: planning

When complete, ask the user to approve proceeding to planning. Then call re_feature_advance_phase with brainstorm path and approval evidence.`, 
    tools: ["read", "bash", "ask_user_question", "issue_tracker", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [{ key: "brainstormDoc", description: "Brainstorm document path", required: true }],
    exitCriteria: [
      "Brainstorm document exists under docs/brainstorms/**",
      "Document includes feature summary, context/constraints, approaches considered, recommendation, key decisions, open questions, and next step",
      "Linked source issue/context/ADR constraints incorporated where relevant",
      "Brainstorm document created/updated and path recorded with re_feature_record_artifact",
      "User approved proceeding to planning",
      "No direct file writes were used; brainstorm document was created/updated through re_feature_record_artifact",
      "No implementation code or plan document created",
    ],
  }),
  plan: phase({
    id: "plan",
    title: "Plan",
    objective: "Create an implementation plan from the brainstorm and project context.",
    prompt: `You are in Phase: plan.

Objective:
Create a concrete implementation plan from the approved brainstorm, gathered context, linked issue, and relevant ADR constraints.

Strict rules:
- Do not implement code.
- Do not edit production files.
- Do not use general write/edit tools; create or update the plan document only through re_feature_record_artifact.
- Do not write issue JSON files directly; use issue_tracker for issue management.
- Use re_feature_adr when adr.location=repo, otherwise ADR plugin tools, if the plan introduces or depends on architecture decisions.
- If a new architectural decision will be required, mark it explicitly for the update_docs/ADR phase.
- Prefer simple, incremental implementation.
- Keep work order dependency-aware.
- Include testing and validation.
- Include local review/compound-before-PR flow.
- Include artifact recording points.
- Ask the user any final planning questions one at a time.

Required plan document:
docs/plans/YYYY-MM-DD-<topic>-plan.md

Document must include:
- Summary
- Requirements / acceptance criteria
- Context and constraints
- Relevant ADRs / architectural implications
- Implementation tasks in dependency order
- Testing strategy
- Review/compound strategy before PR creation
- Rollback or failure handling where relevant
- Open questions
- Explicit next step: implementation

Create/update and record the plan document through re_feature_record_artifact using key planDoc. When complete, ask the user to approve proceeding to implementation. Then call re_feature_advance_phase with plan path and approval evidence.`,
    tools: ["read", "bash", "ask_user_question", "issue_tracker", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [{ key: "planDoc", description: "Plan document path", required: true }],
    exitCriteria: [
      "Plan document exists under docs/plans/**",
      "Plan references the approved brainstorm when one exists",
      "Plan includes requirements/acceptance criteria",
      "Plan includes relevant context/constraints and ADR implications",
      "Plan breaks work into dependency-ordered tasks",
      "Plan includes testing strategy",
      "Plan includes local review + compound-before-PR strategy",
      "Plan identifies artifact recording points",
      "Plan lists open questions or states none",
      "Plan document created/updated and path recorded with re_feature_record_artifact",
      "User approved proceeding to implementation",
      "No direct file writes were used; plan document was created/updated through re_feature_record_artifact",
      "No implementation code modified",
    ],
  }),
  implement: phase({
    id: "implement",
    title: "Implement",
    objective: "Implement the approved plan in the recorded worktree with tests, issue updates, and local commits only.",
    prompt: `You are in Phase: implement.

Objective:
Implement the approved plan in the recorded worktree/branch.

Inputs:
- Linked source issue, if any
- Approved plan document
- Brainstorm document, if any
- Context summary and ADR constraints
- Recorded worktree path and branch name

Strict rules:
- Work only inside the recorded worktree path.
- Follow the plan in dependency order.
- Do not push.
- Do not create a PR.
- Do not merge.
- Package installation commands are allowed in this phase when needed.
- Use issue_tracker for issue management; never write .pi/issues files directly.
- Use re_feature_adr when adr.location=repo, otherwise ADR plugin tools, whenever implementation touches architectural decisions or constraints.
- If a new architectural decision is made, record it as a note/artifact for update_docs; do not create ADRs yet unless explicitly allowed.
- Prefer existing code patterns.
- Add/update tests for behavior changes.
- Run relevant tests after meaningful changes.
- Commit local logical units when tests pass.
- Do not leave completed tracked issues open.

Task loop:
1. Read relevant plan section and referenced files.
2. Inspect existing patterns.
3. Implement smallest logical unit.
4. Add/update tests.
5. Run focused tests.
6. Update issue_tracker when task/finding state changes.
7. Commit when a complete logical unit passes.

Before advancing, record implementationSummary and testsRun with re_feature_record_artifact.`,
    tools: ["read", "bash", "write", "edit", "issue_tracker", "subagent", ...lifecycleTools],
    allowedWriteGlobs: ["**"],
    blockedWriteGlobs: [".git/**", "node_modules/**", ".env*"],
    bashPolicy: {},
    requiredArtifacts: [
      { key: "implementationSummary", description: "Summary of implementation changes", required: true },
      { key: "testsRun", description: "Tests/quality checks run and results", required: true },
    ],
    exitCriteria: [
      "Work happened in recorded worktree/branch",
      "Planned implementation tasks completed or explicitly deferred",
      "Code/tests/docs changed according to plan",
      "Relevant tests run and results summarized",
      "implementationSummary recorded with re_feature_record_artifact",
      "testsRun recorded with re_feature_record_artifact",
      "issue_tracker updated for completed/new tasks",
      "New architectural decisions noted for update_docs/ADR phase",
      "Local commits created for complete logical units, or uncommitted state explicitly justified",
      "No direct .pi/issues writes",
      "No git push",
      "No PR created",
      "No merge performed",
    ],
  }),
  local_review: phase({
    id: "local_review",
    title: "Local Review",
    objective: "Run local/multi-agent review before PR creation, capture findings, and loop back to implementation when issues are found.",
    prompt: `You are in Phase: local_review.

Objective:
Run local review before any push or PR creation. Capture findings through issue_tracker and a review artifact. If actionable issues are found, the workflow must advance to address_findings before compound.

Strict rules:
- Do not implement fixes in this phase.
- Do not push.
- Do not create a PR.
- Do not merge.
- Use issue_tracker for all findings; never write .pi/issues files directly.
- Use re_feature_adr when adr.location=repo, otherwise ADR plugin tools, when review findings touch architectural decisions or constraints.
- Use available review subagents/tools according to the selected strategy.
- Create/update the review findings artifact only through re_feature_record_artifact using key reviewFindingsPath.

Review requirements:
- Run the configured local review depth for the strategy.
- Capture every actionable finding in issue_tracker with severity/priority.
- Clearly distinguish blocking issues from non-blocking notes.
- If there are open actionable findings, call re_feature_advance_phase with evidence that indicates the workflow should go to address_findings.
- Only proceed to compound when there are no open actionable findings, or all remaining findings are explicitly accepted/deferred by the user.

When complete, record reviewFindingsPath and call re_feature_advance_phase with review summary and finding status.`,
    tools: ["read", "bash", "issue_tracker", "subagent", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [{ key: "reviewFindingsPath", description: "Review findings artifact or issue tracker summary" }],
    exitCriteria: [
      "Review run according to selected strategy",
      "Findings captured through issue_tracker",
      "Review findings artifact created/updated through re_feature_record_artifact",
      "Blocking/actionable findings cause transition to address_findings before compound",
      "Only non-actionable, accepted, or deferred findings remain before proceeding",
      "No implementation fixes made in this phase",
      "No push/PR/merge performed",
    ],
    failureNext: "address_findings",
    loopWhen: "Open actionable review findings exist", 
  }),
  compound: phase({
    id: "compound",
    title: "Compound",
    objective: "Capture reusable knowledge before PR creation without direct file writes.",
    prompt: `You are in Phase: compound.

Objective:
Capture reusable knowledge from the implementation and local review before PR creation.

Inputs:
- Approved plan
- Implementation summary
- Tests run
- Local review findings
- Relevant ADR constraints and new decisions noted during implementation

Strict rules:
- Do not implement code.
- Do not fix review findings here.
- Do not push.
- Do not create a PR.
- Do not merge.
- Do not use general write/edit tools.
- Use memory_write for durable lessons/patterns when applicable.
- Create/update the solution document only through re_feature_record_artifact using key solutionDoc.
- Use re_feature_adr when adr.location=repo, otherwise ADR plugin tools, when capturing architectural knowledge or discovering decisions that need ADR updates.
- If an architectural decision was made, record it for update_docs/ADR phase; do not create final ADRs here unless explicitly allowed.

Required solution document:
docs/solutions/YYYY-MM-DD-<topic>-solution.md

Document should include:
- Problem solved
- Approach taken
- Key files/components changed
- Important implementation details
- Tests/validation performed
- Review findings and how they were addressed or deferred
- Reusable lessons/patterns
- ADRs to create/update later, if any

Create/update and record the solution document through re_feature_record_artifact using key solutionDoc. Then call re_feature_advance_phase with evidence.`,
    tools: ["read", "bash", "memory_write", "issue_tracker", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [{ key: "solutionDoc", description: "Solution/compound artifact" }],
    exitCriteria: [
      "Solution document exists under docs/solutions/** if compound is enabled",
      "Solution document created/updated through re_feature_record_artifact",
      "memory_write called for durable reusable learning where applicable, or explicitly not needed",
      "Review findings and implementation lessons captured",
      "New ADR needs recorded for update_docs phase",
      "No direct file writes used",
      "No code changes made",
      "No push/PR/merge performed",
    ],
  }),
  address_findings: phase({
    id: "address_findings",
    title: "Address Findings",
    objective: "Implement fixes for local review findings in the recorded worktree before compound and PR creation.",
    prompt: `You are in Phase: address_findings.

Objective:
Act as a focused implementation-fix phase after local_review and before compound. Fix or explicitly defer actionable review findings in the recorded worktree.

Strict rules:
- This phase is a proxy for implement, scoped to review findings.
- Work only inside the recorded worktree path.
- Do not push.
- Do not create a PR.
- Do not merge.
- Package installation commands are allowed when needed for fixes.
- Use issue_tracker for finding state; never write .pi/issues files directly.
- Use re_feature_adr when adr.location=repo, otherwise ADR plugin tools, whenever a finding or fix touches architectural decisions or constraints.
- Add/update tests for fixes.
- Run relevant tests after fixes.
- Commit local logical fix units when tests pass.
- Close fixed issue_tracker findings immediately; defer/accept only with explicit user approval.

Before advancing, update implementationSummary and testsRun with re_feature_record_artifact to summarize fixes and validation. The next phase should normally return to local_review for verification before compound.`,
    tools: ["read", "bash", "write", "edit", "issue_tracker", "subagent", ...lifecycleTools],
    allowedWriteGlobs: ["**"],
    blockedWriteGlobs: [".git/**", "node_modules/**", ".env*"],
    bashPolicy: {},
    requiredArtifacts: [
      { key: "implementationSummary", description: "Summary of finding fixes", required: true },
      { key: "testsRun", description: "Tests/quality checks rerun and results", required: true },
    ],
    exitCriteria: [
      "Work happened in recorded worktree/branch",
      "P1 findings fixed",
      "P2 findings fixed or explicitly user-deferred/accepted",
      "issue_tracker updated for every addressed/deferred finding",
      "Relevant tests rerun and results summarized",
      "implementationSummary updated with re_feature_record_artifact",
      "testsRun updated with re_feature_record_artifact",
      "Fix commits created for complete logical units, or uncommitted state explicitly justified",
      "No direct .pi/issues writes",
      "No git push",
      "No PR created",
      "No merge performed",
    ],
    next: "local_review",
  }),
  push_branch: phase({
    id: "push_branch",
    title: "Push Branch",
    objective: "Push the reviewed, locally validated feature branch to remote.",
    prompt: `You are in Phase: push_branch.

Objective:
Push the reviewed and locally validated feature branch to the remote.

Inputs:
- Recorded worktree path
- Recorded branch name
- Implementation summary
- Tests run
- Local review status
- Compound/solution artifact

Strict rules:
- Do not edit files.
- Do not create a PR.
- Do not merge.
- Only push the recorded branch from the recorded worktree.
- Verify the branch and worktree before pushing.
- Verify review/compound gates were completed or explicitly bypassed.
- Do not use --force or -f.
- Do not use --no-verify.
- If push fails due to legitimate remote state, stop and report; do not force-push automatically.

Required checks before push:
- git status
- confirm current branch equals recorded branch
- confirm remote exists
- confirm no unexpected uncommitted changes, or explicitly document them
- confirm local review has no unresolved blocking findings
- confirm compound is complete or strategy skipped it

After pushing, record pushSummary with re_feature_record_artifact. Then call re_feature_advance_phase with push evidence.`,
    tools: ["read", "bash", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: {
      allowedPatterns: [
        "^\\s*pwd\\s*$",
        "^\\s*git\\s+(status|branch|log|diff|remote|rev-parse|push)(\\s|$)",
      ],
    },
    requiredArtifacts: [{ key: "pushSummary", description: "Summary of pushed branch and remote tracking", required: true }],
    exitCriteria: [
      "Running from recorded worktree",
      "Current branch matches recorded branch",
      "Branch pushed to remote",
      "Upstream tracking set",
      "pushSummary recorded with re_feature_record_artifact",
      "No force push used",
      "No --no-verify used",
      "No PR created",
      "No merge performed",
    ],
  }),
  create_pr: phase({
    id: "create_pr",
    title: "Create PR",
    objective: "Create the pull request with summary, testing, context, and artifact links.",
    prompt: `You are in Phase: create_pr.

Objective:
Create the pull request for the already pushed branch.

Strict rules:
- Do not edit files.
- Do not push additional changes unless explicitly routed back to address_findings/push_branch.
- Do not merge.
- Use gh pr create/view only.
- PR body must include summary, testing, context links, source issue if any, brainstorm/plan/solution artifact links when available, and note that local review/compound happened before PR creation.

After PR creation, record prUrl, prNumber when known, and prSummary with re_feature_record_artifact. Then call re_feature_advance_phase.`,
    tools: ["read", "bash", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: { allowedPatterns: ["^\\s*gh\\s+pr\\s+(create|view)(\\s|$)", "^\\s*git\\s+(status|log|diff|branch|rev-parse)(\\s|$)"] },
    requiredArtifacts: [
      { key: "prUrl", description: "Pull request URL", required: true },
      { key: "prSummary", description: "Summary of created PR", required: true },
    ],
    exitCriteria: [
      "PR number/URL recorded",
      "prSummary recorded with re_feature_record_artifact",
      "PR body includes summary, testing, context, and artifact links",
      "PR body references local review/compound-before-PR flow",
      "No merge performed",
    ],
  }),
  pr_verification: phase({
    id: "pr_verification",
    title: "PR Verification",
    objective: "Verify PR checks and route failures back to address_findings.",
    prompt: `You are in Phase: pr_verification.

Objective:
Verify PR status/checks after creation.

Strict rules:
- Do not edit files.
- Do not merge until checks are known and acceptable.
- If CI/checks fail, do not fix here; advance/request transition back to address_findings.
- Use gh pr checks/view and gh run list/watch to inspect status.

Record prVerificationSummary with re_feature_record_artifact. If checks are green or explicitly bypassed, advance to merge. If failures require fixes, request/address transition to address_findings.`,
    tools: ["read", "bash", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: { allowedPatterns: ["^\\s*gh\\s+(pr\\s+(checks|view)|run\\s+(list|watch))(\\s|$)", "^\\s*git\\s+(status|log|diff)(\\s|$)"] },
    requiredArtifacts: [{ key: "prVerificationSummary", description: "PR checks/status summary", required: true }],
    exitCriteria: [
      "CI/check status known",
      "prVerificationSummary recorded with re_feature_record_artifact",
      "Green checks or user-approved bypass before merge",
      "Failed checks route back to address_findings",
    ],
  }),
  merge: phase({
    id: "merge",
    title: "Merge",
    objective: "Merge or enable automerge according to the selected strategy.",
    prompt: `You are in Phase: merge.

Objective:
Merge the verified PR or enable automerge according to strategy.

Strict rules:
- Do not edit files.
- Confirm PR verification is complete or explicitly bypassed.
- For security-first strategy, require explicit user approval before merge/automerge.
- Use gh pr merge/view/checks only.

After merge/automerge, record mergeSummary with re_feature_record_artifact and advance.`,
    tools: ["read", "bash", "ask_user_question", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: { allowedPatterns: ["^\\s*gh\\s+pr\\s+(merge|view|checks)(\\s|$)"] },
    requiredArtifacts: [{ key: "mergeSummary", description: "Merge or automerge status", required: true }],
    exitCriteria: [
      "PR verification complete or bypassed",
      "Merge/automerge status recorded with re_feature_record_artifact",
      "Security-first manual approval honored",
    ],
  }),
  update_docs: phase({
    id: "update_docs",
    title: "Update Documentation",
    objective: "Update dev logs, ADRs, README/API docs, and other affected documentation after merge/automerge.",
    prompt: `You are in Phase: update_docs.

Objective:
Update documentation and knowledge records after merge/automerge.

Strict rules:
- Only edit documentation/ADR/dev-log/reference files.
- Use repo ADR files when adr.location=repo, otherwise ADR plugin tools, for ADR creation/update when architectural decisions were made.
- Use memory_write for durable lessons if not already captured.
- Use issue_tracker for issue updates; never write .pi/issues files directly.
- Do not change implementation code.

Record docsSummary with re_feature_record_artifact before advancing.`,
    tools: ["read", "bash", "write", "edit", "memory_write", "issue_tracker", ...lifecycleTools],
    allowedWriteGlobs: ["docs/**", "README.md", "commands/**", "references/**"],
    bashPolicy: readOnlyBash,
    requiredArtifacts: [{ key: "docsSummary", description: "Documentation/ADR/dev-log update summary", required: true }],
    exitCriteria: [
      "Required docs updated",
      "ADR/dev-log decisions recorded when applicable",
      "docsSummary recorded with re_feature_record_artifact",
      "No implementation code changed",
    ],
  }),
  cleanup: phase({
    id: "cleanup",
    title: "Cleanup",
    objective: "Clean up worktree/branch state or record why it is retained.",
    prompt: `You are in Phase: cleanup.

Objective:
Clean up the feature worktree/branch state after merge/docs, or record why it is intentionally retained.

Strict rules:
- Do not edit files.
- Only run git worktree/branch cleanup commands that are safe for the recorded worktree/branch.
- Do not delete unmerged work unless merge/automerge status is clear or user bypasses.

Record cleanupSummary with re_feature_record_artifact before advancing.`,
    tools: ["read", "bash", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: { allowedPatterns: ["^\\s*git\\s+(status|worktree|branch)(\\s|$)"] },
    requiredArtifacts: [{ key: "cleanupSummary", description: "Cleanup result or retention reason", required: true }],
    exitCriteria: [
      "Worktree cleaned or intentionally retained",
      "cleanupSummary recorded with re_feature_record_artifact",
    ],
  }),
  summary: phase({
    id: "summary",
    title: "Summary",
    objective: "Present final workflow summary to the user.",
    prompt: `You are in Phase: summary.

Objective:
Present the final enforced /re-feature workflow summary to the user.

Include:
- Feature and source issue
- Strategy
- Branch/worktree
- Brainstorm/plan/solution artifacts
- Implementation summary and tests
- Review/finding status
- PR URL and merge status
- Docs/ADR/memory updates
- Cleanup status
- Bypasses, if any

After presenting the summary, call re_feature_advance_phase to complete the workflow.`,
    tools: ["read", ...lifecycleTools],
    allowedWriteGlobs: [],
    bashPolicy: { readOnly: true },
    requiredArtifacts: [],
    exitCriteria: ["Final summary emitted"],
  }),
};

export function getPhase(id: PhaseId): PhaseDefinition {
  return PHASES[id];
}

export function getNextPhaseId(id: PhaseId): PhaseId | undefined {
  const index = PHASE_ORDER.indexOf(id);
  return index >= 0 ? PHASE_ORDER[index + 1] : undefined;
}
