import { relative, resolve } from "node:path";
import type { PhaseId, ResolvedPhase, ReFeatureState } from "./types.js";

const phaseIndex: Record<PhaseId, number> = {
  select_strategy: -1,
  gather_context: 0,
  clarify_feature: 1,
  create_worktree: 2,
  brainstorm: 3,
  plan: 4,
  implement: 5,
  local_review: 6,
  address_findings: 7,
  compound: 8,
  push_branch: 9,
  create_pr: 10,
  pr_verification: 11,
  merge: 12,
  update_docs: 13,
  cleanup: 14,
  summary: 15,
};

export function isAtLeastPhase(current: PhaseId, required: PhaseId): boolean {
  return phaseIndex[current] >= phaseIndex[required];
}

function globToRegExp(glob: string): RegExp {
  const escaped = glob
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*\*/g, "__DOUBLE_STAR__")
    .replace(/\*/g, "[^/]*")
    .replace(/__DOUBLE_STAR__/g, ".*");
  return new RegExp(`^${escaped}$`);
}

export function matchesAnyGlob(path: string, globs: string[]): boolean {
  const normalized = path.replace(/\\/g, "/").replace(/^\.\//, "");
  return globs.some((glob) => glob === "**" || globToRegExp(glob).test(normalized));
}

export function checkWriteAllowed(cwd: string, filePath: string, phase: ResolvedPhase, state?: ReFeatureState): string | undefined {
  const baseDir = state?.worktreePath && ["implement", "address_findings"].includes(phase.id) ? resolve(cwd, state.worktreePath) : cwd;
  const absolute = resolve(baseDir, filePath);
  const relToBase = relative(baseDir, absolute).replace(/\\/g, "/");
  if (relToBase.startsWith("..")) {
    return `Writes outside ${state?.worktreePath && ["implement", "address_findings"].includes(phase.id) ? "recorded worktree" : "workflow cwd"} are blocked in phase ${phase.id}: ${filePath}`;
  }
  const relToWorkflow = relative(cwd, absolute).replace(/\\/g, "/");
  const policyRel = state?.worktreePath && ["implement", "address_findings"].includes(phase.id) ? relToBase : relToWorkflow;
  if (phase.blockedWriteGlobs?.length && (matchesAnyGlob(policyRel, phase.blockedWriteGlobs) || matchesAnyGlob(relToWorkflow, phase.blockedWriteGlobs))) {
    return `Writes to ${policyRel} are explicitly blocked in phase ${phase.id}.`;
  }
  if (!phase.allowedWriteGlobs.length || !matchesAnyGlob(policyRel, phase.allowedWriteGlobs)) {
    return `Writes are restricted in phase ${phase.id}. Allowed globs: ${phase.allowedWriteGlobs.join(", ") || "none"}. Attempted: ${policyRel}`;
  }
  return undefined;
}

export function checkBashAllowed(command: string, phase: ResolvedPhase): string | undefined {
  const destructive = [/\brm\s+-rf\s+\//, /\bsudo\s+rm\b/, /\bmkfs\b/, /\bdd\s+if=/, /\bchmod\s+-R\s+777\b/];
  if (destructive.some((pattern) => pattern.test(command))) {
    return "Destructive shell command blocked by re-feature policy.";
  }
  if (/\bgit\s+push\b/.test(command) && /\s(--force|-f)(\s|$)/.test(command)) {
    return "Force push requires an explicit /re-feature bypass and is blocked by default.";
  }
  if (/\bgit\s+push\b/.test(command) && /\s--no-verify(\s|$)/.test(command)) {
    return "git push --no-verify is blocked by re-feature policy.";
  }
  if (/\bgit\s+push\b/.test(command) && !isAtLeastPhase(phase.id, "push_branch")) {
    return `git push is blocked until phase push_branch. Current phase: ${phase.id}`;
  }
  if (/\bgh\s+pr\s+create\b/.test(command) && !isAtLeastPhase(phase.id, "create_pr")) {
    return `gh pr create is blocked until phase create_pr. Current phase: ${phase.id}`;
  }
  if (/\bgh\s+pr\s+merge\b/.test(command) && !isAtLeastPhase(phase.id, "merge")) {
    return `gh pr merge is blocked until phase merge. Current phase: ${phase.id}`;
  }
  if (/\b(npm|pnpm|bun|yarn)\s+(install|add)\b|\bnpm\s+i\b/.test(command) && !["implement", "address_findings"].includes(phase.id)) {
    return `Package installation is only open during implementation/fix phases. Current phase: ${phase.id}`;
  }
  if (phase.bashPolicy.blockedPatterns?.some((pattern) => new RegExp(pattern).test(command))) {
    return `Command blocked by phase ${phase.id} bash policy.`;
  }
  if (phase.bashPolicy.allowedPatterns?.length) {
    const allowed = phase.bashPolicy.allowedPatterns.some((pattern) => new RegExp(pattern).test(command));
    if (!allowed) return `Command is not allowlisted in phase ${phase.id}.`;
  }
  if (phase.bashPolicy.readOnly && /\b(git\s+(commit|checkout|switch|reset|clean|push)|npm\s+install|pnpm\s+install|bun\s+install|rm\b|mv\b|cp\b|mkdir\b|touch\b)/.test(command)) {
    return `Command appears mutating but phase ${phase.id} is read-only.`;
  }
  return undefined;
}
