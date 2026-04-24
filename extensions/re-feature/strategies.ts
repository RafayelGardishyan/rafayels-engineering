import { PHASES } from "./phases.js";
import type { PhaseId, ResolvedPhase, StrategyDefinition } from "./types.js";

export const STRATEGIES: Record<string, StrategyDefinition> = {
  "full-process": {
    id: "full-process",
    title: "Full Process",
    description: "Complete production feature process with strict gates, local review, compound, PR, docs, and cleanup.",
    strictness: "strict",
    phaseOverrides: {},
  },
  "quick-spike": {
    id: "quick-spike",
    title: "Quick Spike",
    description: "Fast prototype path with brainstorm/compound/docs disabled by default and lighter review.",
    strictness: "strict",
    phaseOverrides: {
      brainstorm: { enabled: false },
      plan: { guidance: "Minimal plan only. Skip external research." },
      local_review: { guidance: "Shallow review only: security and simplicity checks." },
      compound: { enabled: false },
      update_docs: { enabled: false },
    },
  },
  "security-first": {
    id: "security-first",
    title: "Security First",
    description: "Maximum rigor for auth, payments, PII, credentials, and compliance-sensitive work.",
    strictness: "strict",
    phaseOverrides: {
      brainstorm: { guidance: "Include threat modeling questions and attack surface analysis." },
      plan: { guidance: "Mandatory security section and input validation strategy." },
      implement: { guidance: "Sequential work only. Validate all inputs. Tests required at every commit." },
      local_review: { guidance: "Block on any unresolved security finding." },
      merge: { guidance: "No automerge. Require explicit human approval." },
    },
  },
  "review-only": {
    id: "review-only",
    title: "Review Only",
    description: "Audit existing code or PRs without implementation unless the user explicitly opts into fixes.",
    strictness: "strict",
    phaseOverrides: {
      brainstorm: { enabled: false },
      plan: { enabled: false },
      implement: { enabled: false },
      compound: { enabled: "optional" },
      address_findings: { enabled: "optional" },
      push_branch: { enabled: false },
      create_pr: { enabled: false },
      pr_verification: { enabled: false },
      merge: { enabled: false },
      update_docs: { enabled: "optional" },
    },
  },
};

export function getStrategy(id: string): StrategyDefinition | undefined {
  return STRATEGIES[id];
}

export function listStrategies(): StrategyDefinition[] {
  return Object.values(STRATEGIES);
}

export function resolvePhase(phaseId: PhaseId, strategy: StrategyDefinition): ResolvedPhase {
  const base = PHASES[phaseId];
  const override = strategy.phaseOverrides[phaseId];
  return {
    ...base,
    tools: override?.tools ?? base.tools,
    allowedWriteGlobs: override?.allowedWriteGlobs ?? base.allowedWriteGlobs,
    bashPolicy: { ...base.bashPolicy, ...(override?.bashPolicy ?? {}) },
    exitCriteria: override?.exitCriteria ?? base.exitCriteria,
    enabled: override?.enabled ?? true,
    strategyGuidance: override?.guidance,
  };
}
