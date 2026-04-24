import { Type } from "@mariozechner/pi-ai";
import type { ExtensionAPI, ExtensionCommandContext, ExtensionContext } from "@mariozechner/pi-coding-agent";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { PHASES, getNextPhaseId } from "./phases.js";
import { checkBashAllowed, checkWriteAllowed } from "./policies.js";
import { listStrategies, getStrategy, resolvePhase } from "./strategies.js";
import { STATE_CUSTOM_TYPE, applyValidatorArtifacts, createInitialState, recordBypass, restoreLatestState, transitionState } from "./state.js";
import { runValidator } from "./validator.js";
import type { BypassKind, PhaseId, ReFeatureSourceIssue, ReFeatureState, StrategyDefinition } from "./types.js";

const ADR_TOOLS = ["semantic_search", "get_adr", "query_graph", "list_adrs", "list_connections"];
const LIFECYCLE_TOOLS = ["re_feature_status", "re_feature_record_artifact", "re_feature_advance_phase", "re_feature_request_bypass", ...ADR_TOOLS];

type IssueRecord = {
  id: string;
  title: string;
  status: "open" | "closed";
  priority?: string;
  tags?: string[];
};

function parseArgs(args: string): { description: string; strategy?: string; issueId?: string } {
  const strategy = args.match(/(?:^|\s)--strategy=([^\s]+)/)?.[1];
  const issueId = args.match(/(?:^|\s)--issue=([^\s]+)/)?.[1];
  const description = args
    .replace(/(?:^|\s)--strategy=[^\s]+/g, "")
    .replace(/(?:^|\s)--issue=[^\s]+/g, "")
    .trim();
  return { description, strategy, issueId };
}

function listOpenIssues(cwd: string): IssueRecord[] {
  const dir = join(cwd, ".pi", "issues");
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((entry) => entry.endsWith(".json"))
    .map((entry) => {
      try {
        return JSON.parse(readFileSync(join(dir, entry), "utf8")) as IssueRecord;
      } catch {
        return undefined;
      }
    })
    .filter((issue): issue is IssueRecord => Boolean(issue && issue.status === "open"))
    .sort((a, b) => a.id.localeCompare(b.id));
}

async function selectSourceIssue(ctx: ExtensionCommandContext, requestedIssueId?: string): Promise<ReFeatureSourceIssue | undefined> {
  const issues = listOpenIssues(ctx.cwd);
  if (requestedIssueId) {
    const issue = issues.find((candidate) => candidate.id === requestedIssueId);
    if (issue) return { id: issue.id, title: issue.title, priority: issue.priority, tags: issue.tags };
    ctx.ui.notify(`Requested issue ${requestedIssueId} was not found among open issues.`, "warning");
  }
  if (!ctx.hasUI || issues.length === 0) return undefined;
  const labels = ["No source issue", ...issues.map((issue) => `${issue.id}: ${issue.title} (${issue.priority ?? "p2"})`)];
  const selected = await ctx.ui.select("Link this /re-feature run to an open issue?", labels);
  if (!selected || selected === "No source issue") return undefined;
  const index = labels.indexOf(selected) - 1;
  const issue = issues[index];
  return issue ? { id: issue.id, title: issue.title, priority: issue.priority, tags: issue.tags } : undefined;
}

function formatPhaseContext(state: ReFeatureState, strategy: StrategyDefinition): string {
  const phase = resolvePhase(state.phaseId, strategy);
  return `[RE-FEATURE ENFORCED WORKFLOW ACTIVE]\n\nCurrent phase: ${phase.id} — ${phase.title}\nStrategy: ${strategy.title} (${strategy.id})\nFeature: ${state.featureDescription}\nSource issue: ${state.sourceIssue ? `${state.sourceIssue.id}: ${state.sourceIssue.title}` : "none"}\n\nObjective:\n${phase.objective}\n\nPhase prompt:\n${phase.prompt}\n${phase.strategyGuidance ? `\nStrategy guidance:\n${phase.strategyGuidance}\n` : ""}\nStrict enforcement:\n- Allowed write globs: ${phase.allowedWriteGlobs.join(", ") || "none"}\n- ADR plugin tools are available in every phase when loaded; use them whenever a phase uncovers or depends on architectural decisions.\n- Record artifacts with re_feature_record_artifact as soon as they are known.\n- Phase-gated commands are enforced. git push requires push_branch; gh pr create requires create_pr; gh pr merge requires merge.\n- To bypass a gate, use re_feature_request_bypass and obtain explicit user approval.\n\nExit criteria:\n${phase.exitCriteria.map((criterion) => `- ${criterion}`).join("\n")}\n\nWhen this phase is complete, call re_feature_advance_phase with concrete evidence. Do not proceed to the next phase without that tool approving the transition.`;
}

function statusText(state: ReFeatureState): string {
  const phase = PHASES[state.phaseId];
  return `re:feature · ${phase.id}`;
}

function getNextEnabledPhase(current: PhaseId, strategy: StrategyDefinition): PhaseId | undefined {
  const configuredNext = PHASES[current].next;
  let next = configuredNext ?? getNextPhaseId(current);
  while (next) {
    const resolved = resolvePhase(next, strategy);
    if (resolved.enabled !== false) return next;
    next = getNextPhaseId(next);
  }
  return undefined;
}

function safeActiveTools(pi: ExtensionAPI, desired: string[]): string[] {
  const available = new Set(pi.getAllTools().map((tool) => tool.name));
  return Array.from(new Set(desired)).filter((name) => available.has(name));
}

export default function reFeatureExtension(pi: ExtensionAPI) {
  let state: ReFeatureState | undefined;
  let previousActiveTools: string[] | undefined;

  function persist(next: ReFeatureState) {
    state = next;
    pi.appendEntry(STATE_CUSTOM_TYPE, next);
  }

  function applyPhaseTools(ctx?: ExtensionContext) {
    if (!state?.active) return;
    const strategy = getStrategy(state.strategyId) ?? getStrategy("full-process")!;
    const phase = resolvePhase(state.phaseId, strategy);
    const tools = safeActiveTools(pi, [...phase.tools, ...LIFECYCLE_TOOLS]);
    if (tools.length > 0) pi.setActiveTools(tools);
    ctx?.ui.setStatus("re-feature", statusText(state));
    ctx?.ui.setWidget("re-feature", [
      `re-feature: ${phase.title}`,
      `strategy: ${strategy.id}`,
      `issue: ${state.sourceIssue ? state.sourceIssue.id : "none"}`,
      `advance: call re_feature_advance_phase`,
    ]);
  }

  pi.registerCommand("re-feature", {
    description: "Start the enforced Rafayel Engineering feature pipeline",
    handler: async (args: string, ctx: ExtensionCommandContext) => {
      const parsed = parseArgs(args);
      const sourceIssue = await selectSourceIssue(ctx, parsed.issueId);
      let description = parsed.description;
      if (!description && sourceIssue) description = sourceIssue.title;
      if (!description && ctx.hasUI) {
        const answer = await ctx.ui.input("What feature should /re-feature implement?", "Describe the feature...");
        description = answer?.trim() ?? "";
      }
      if (!description) {
        ctx.ui.notify("/re-feature requires a description or selected issue.", "error");
        return;
      }

      let strategyId = parsed.strategy;
      if (!strategyId && ctx.hasUI) {
        const choices = listStrategies().map((strategy) => `${strategy.id}: ${strategy.description}`);
        const selected = await ctx.ui.select("Which workflow strategy should /re-feature use?", choices);
        strategyId = selected?.split(":", 1)[0];
      }
      strategyId ||= "full-process";
      const strategy = getStrategy(strategyId);
      if (!strategy) {
        ctx.ui.notify(`Unknown strategy: ${strategyId}`, "error");
        return;
      }

      previousActiveTools = pi.getActiveTools();
      const initial = createInitialState({
        cwd: ctx.cwd,
        featureDescription: description,
        strategyId,
        strategyLabel: strategy.title,
        phaseId: "gather_context",
        sourceIssue,
      });
      persist(initial);
      pi.setSessionName(`re-feature: ${description.slice(0, 60)}`);
      applyPhaseTools(ctx);
      pi.sendUserMessage(`Begin enforced /re-feature workflow for: ${description}\n\nCurrent phase: gather_context. Use re_feature_status if needed. When ready to advance, call re_feature_advance_phase.`);
    },
  });

  pi.registerCommand("re-feature-status", {
    description: "Show current enforced /re-feature state",
    handler: async (_args, ctx) => {
      if (!state?.active) {
        ctx.ui.notify("No active /re-feature workflow.", "info");
        return;
      }
      const strategy = getStrategy(state.strategyId) ?? getStrategy("full-process")!;
      const phase = resolvePhase(state.phaseId, strategy);
      ctx.ui.notify(`${formatPhaseContext(state, strategy)}\n\nAllowed tools:\n${phase.tools.join(", ")}\n\nBypasses: ${state.bypasses.length}`, "info");
    },
  });

  pi.registerCommand("re-feature-bypass", {
    description: "Manually record a user-approved /re-feature bypass",
    handler: async (args, ctx) => {
      if (!state?.active) {
        ctx.ui.notify("No active /re-feature workflow.", "error");
        return;
      }
      const reason = args.trim() || (await ctx.ui.input("Why bypass this /re-feature gate?", "Reason..."))?.trim();
      if (!reason) return;
      persist(recordBypass(state, { kind: "policy", reason }));
      ctx.ui.notify("Bypass recorded.", "warning");
    },
  });

  pi.registerCommand("re-feature-abort", {
    description: "Abort the active enforced /re-feature workflow",
    handler: async (_args, ctx) => {
      if (!state?.active) return;
      const ok = !ctx.hasUI || (await ctx.ui.confirm("Abort /re-feature?", "Disable enforcement for this workflow?"));
      if (!ok) return;
      persist({ ...state, active: false, updatedAt: Date.now() });
      if (previousActiveTools) pi.setActiveTools(previousActiveTools);
      ctx.ui.setStatus("re-feature", undefined);
      ctx.ui.setWidget("re-feature", undefined);
      ctx.ui.notify("/re-feature enforcement aborted.", "warning");
    },
  });

  pi.registerTool<any>({
    name: "re_feature_status",
    label: "Re Feature Status",
    description: "Return current enforced /re-feature workflow phase, requirements, issue link, and artifacts.",
    parameters: Type.Object({}),
    async execute() {
      if (!state?.active) return { content: [{ type: "text", text: "No active /re-feature workflow." }], details: { active: false } };
      const strategy = getStrategy(state.strategyId) ?? getStrategy("full-process")!;
      const phase = resolvePhase(state.phaseId, strategy);
      return {
        content: [{ type: "text", text: formatPhaseContext(state, strategy) }],
        details: { active: true, state, phase },
      };
    },
  });

  pi.registerTool<any>({
    name: "re_feature_record_artifact",
    label: "Re Feature Record Artifact",
    description: "Record an artifact or workflow state value for the active enforced /re-feature run.",
    parameters: Type.Object({
      key: Type.String({ description: "Artifact key, e.g. contextSummary, brainstormDoc, planDoc, solutionDoc, reviewFindingsPath, implementationSummary, testsRun, pushSummary, prSummary, prVerificationSummary, mergeSummary, docsSummary, cleanupSummary, prNumber, prUrl, devLogPath, adrIds, worktreePath, branchName" }),
      value: Type.Any({ description: "Artifact value to record. For document artifacts, pass either a path string or { path, content } to write through this controlled proxy." }),
    }),
    async execute(_id, params) {
      if (!state?.active) return { content: [{ type: "text", text: "No active /re-feature workflow." }], details: { recorded: false } };
      const key = String(params.key);
      const documentDirs: Record<string, string> = {
        brainstormDoc: "docs/brainstorms",
        planDoc: "docs/plans",
        solutionDoc: "docs/solutions",
        reviewFindingsPath: "docs/reviews",
      };
      const getArtifactPathAndContent = () => {
        if (typeof params.value === "object" && params.value !== null && "path" in params.value) {
          const value = params.value as { path?: unknown; content?: unknown };
          return { path: String(value.path ?? ""), content: typeof value.content === "string" ? value.content : undefined };
        }
        return { path: String(params.value), content: undefined };
      };
      const next = { ...state, artifacts: { ...state.artifacts }, updatedAt: Date.now() } as ReFeatureState;
      if (key === "worktreePath") {
        next.worktreePath = String(params.value);
      } else if (key === "branchName") {
        next.branchName = String(params.value);
      } else if (key === "adrIds") {
        next.artifacts.adrIds = Array.isArray(params.value) ? params.value.map(String) : [String(params.value)];
      } else if (key in documentDirs) {
        const { path, content } = getArtifactPathAndContent();
        const allowedDir = documentDirs[key];
        const absolutePath = resolve(state.cwd, path);
        const relativePath = relative(state.cwd, absolutePath).replace(/\\/g, "/");
        if (relativePath.startsWith("..") || !relativePath.startsWith(`${allowedDir}/`)) {
          return { content: [{ type: "text", text: `${key} must be under ${allowedDir}/. Attempted: ${relativePath}` }], details: { recorded: false, key } };
        }
        if (content !== undefined) {
          mkdirSync(dirname(absolutePath), { recursive: true });
          writeFileSync(absolutePath, content.endsWith("\n") ? content : `${content}\n`, "utf8");
        }
        (next.artifacts as any)[key] = relativePath;
      } else if (key in next.artifacts || ["contextSummary", "implementationSummary", "testsRun", "pushSummary", "prSummary", "prVerificationSummary", "mergeSummary", "docsSummary", "cleanupSummary", "prNumber", "prUrl", "devLogPath"].includes(key)) {
        (next.artifacts as any)[key] = String(params.value);
      } else {
        return { content: [{ type: "text", text: `Unsupported artifact key: ${key}` }], details: { recorded: false, key } };
      }
      persist(next);
      return { content: [{ type: "text", text: `Recorded ${key}.` }], details: { recorded: true, key, state: next } };
    },
  });

  pi.registerTool<any>({
    name: "re_feature_request_bypass",
    label: "Re Feature Request Bypass",
    description: "Ask the user for explicit approval to bypass a strict /re-feature gate and record the audit entry.",
    parameters: Type.Object({
      reason: Type.String({ description: "Why the bypass is needed" }),
      kind: Type.Optional(Type.String({ description: "advance, tool_call, or policy" })),
      details: Type.Optional(Type.Any()),
    }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      if (!state?.active) return { content: [{ type: "text", text: "No active /re-feature workflow." }], details: { approved: false } };
      const approved = ctx.hasUI ? await ctx.ui.confirm("Approve /re-feature bypass?", `Phase: ${state.phaseId}\nReason: ${params.reason}`) : false;
      if (!approved) return { content: [{ type: "text", text: "Bypass denied." }], details: { approved: false } };
      persist(recordBypass(state, { kind: (params.kind as BypassKind | undefined) ?? "policy", reason: params.reason, details: params.details }));
      return { content: [{ type: "text", text: "Bypass approved and recorded." }], details: { approved: true, state } };
    },
  });

  pi.registerTool<any>({
    name: "re_feature_advance_phase",
    label: "Re Feature Advance Phase",
    description: "Validate and advance the current enforced /re-feature phase. Fails closed unless validator passes or user approves bypass.",
    parameters: Type.Object({
      evidence: Type.String({ description: "Concrete evidence that the current phase is complete" }),
      requestedNextPhase: Type.Optional(Type.String({ description: "Optional requested next phase id" })),
    }),
    async execute(_id, params, signal, onUpdate, ctx) {
      if (!state?.active) return { content: [{ type: "text", text: "No active /re-feature workflow." }], details: { advanced: false } };
      const strategy = getStrategy(state.strategyId) ?? getStrategy("full-process")!;
      const phase = resolvePhase(state.phaseId, strategy);
      onUpdate?.({ content: [{ type: "text", text: `Validating phase ${phase.id}...` }], details: {} });
      const validator = await runValidator({ cwd: state.cwd, phase, state, evidence: params.evidence, signal });
      state = applyValidatorArtifacts(state, validator);
      if (!validator.pass) {
        let bypass = false;
        if (ctx.hasUI) {
          bypass = await ctx.ui.confirm("Phase validator failed. Bypass?", `Phase: ${phase.id}\nMissing:\n${validator.missing.map((item) => `- ${item}`).join("\n") || "- unspecified"}\n\nEvidence:\n${params.evidence}`);
        }
        if (!bypass) {
          persist(state);
          return { content: [{ type: "text", text: `Phase ${phase.id} did not pass validation.\nMissing:\n${validator.missing.map((item) => `- ${item}`).join("\n")}` }], details: { advanced: false, validator } };
        }
        state = recordBypass(state, { kind: "advance", reason: `User bypassed validator failure for ${phase.id}`, details: validator });
      }

      const requested = params.requestedNextPhase as PhaseId | undefined;
      let next = requested && PHASES[requested] ? requested : getNextEnabledPhase(state.phaseId, strategy);
      if (state.phaseId === "local_review" && !requested) {
        const openFindings = state.findings.filter((finding) => finding.status === "open" && (finding.severity === "p1" || finding.severity === "p2"));
        const evidenceMentionsIssues = /\b(open|actionable|blocking|p1|p2|issue|finding)s?\b/i.test(params.evidence) && !/\b(no open|no actionable|none open|all (fixed|deferred|accepted))\b/i.test(params.evidence);
        if (openFindings.length > 0 || evidenceMentionsIssues) next = "address_findings";
      }
      if (state.phaseId === "pr_verification" && !requested) {
        const evidenceMentionsFailure = /\b(fail|failed|failure|red|error|broken)\b/i.test(params.evidence) && !/\b(no fail|not failed|all pass|green|passed)\b/i.test(params.evidence);
        if (evidenceMentionsFailure) next = "address_findings";
      }
      if (!next) {
        persist({ ...state, active: false, updatedAt: Date.now() });
        return { content: [{ type: "text", text: "Workflow complete. No next phase." }], details: { advanced: true, complete: true, validator } };
      }
      const advanced = transitionState(state, next, validator, !validator.pass);
      persist(advanced);
      applyPhaseTools(ctx);
      return { content: [{ type: "text", text: `Advanced to ${next}: ${PHASES[next].title}` }], details: { advanced: true, phaseId: next, validator, state: advanced } };
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    state = restoreLatestState(ctx.sessionManager.getEntries());
    if (state?.active) applyPhaseTools(ctx);
  });

  pi.on("before_agent_start", async (_event, _ctx) => {
    if (!state?.active) return;
    const strategy = getStrategy(state.strategyId) ?? getStrategy("full-process")!;
    return { message: { customType: "re-feature-context", content: formatPhaseContext(state, strategy), display: false } };
  });

  pi.on("tool_call", async (event) => {
    if (!state?.active) return;
    const strategy = getStrategy(state.strategyId) ?? getStrategy("full-process")!;
    const phase = resolvePhase(state.phaseId, strategy);
    if (event.toolName === "bash") {
      const reason = checkBashAllowed(String((event.input as any).command ?? ""), phase);
      if (reason) return { block: true, reason };
    }
    if (event.toolName === "write" || event.toolName === "edit") {
      const filePath = String((event.input as any).path ?? (event.input as any).file_path ?? "");
      const reason = checkWriteAllowed(state.cwd, filePath, phase, state);
      if (reason) return { block: true, reason };
    }
  });
}
