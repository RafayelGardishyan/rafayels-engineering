import type { ReFeatureBypass, ReFeatureSourceIssue, ReFeatureState, ValidatorResult, PhaseId } from "./types.js";

export const STATE_CUSTOM_TYPE = "re-feature-state";

export function createInitialState(args: {
  cwd: string;
  featureDescription: string;
  strategyId: string;
  strategyLabel?: string;
  phaseId: PhaseId;
  sourceIssue?: ReFeatureSourceIssue;
}): ReFeatureState {
  const now = Date.now();
  return {
    active: true,
    workflowId: `re-feature-${now}`,
    featureDescription: args.featureDescription,
    strategyId: args.strategyId,
    phaseId: args.phaseId,
    cwd: args.cwd,
    preflight: {
      selectedAt: now,
      strategyId: args.strategyId,
      strategyLabel: args.strategyLabel,
      sourceIssue: args.sourceIssue,
    },
    sourceIssue: args.sourceIssue,
    artifacts: {},
    findings: [],
    bypasses: [],
    history: [{ phaseId: args.phaseId, enteredAt: now }],
    createdAt: now,
    updatedAt: now,
  };
}

export function restoreLatestState(entries: any[]): ReFeatureState | undefined {
  for (let i = entries.length - 1; i >= 0; i--) {
    const entry = entries[i];
    if (entry?.type === "custom" && entry.customType === STATE_CUSTOM_TYPE && entry.data) {
      return entry.data as ReFeatureState;
    }
  }
  return undefined;
}

export function transitionState(state: ReFeatureState, nextPhaseId: PhaseId, validator?: ValidatorResult, bypassed = false): ReFeatureState {
  const now = Date.now();
  const history = [...state.history];
  const current = history[history.length - 1];
  if (current && current.phaseId === state.phaseId && !current.exitedAt) {
    current.exitedAt = now;
    current.validator = validator;
    current.bypassed = bypassed;
  }
  history.push({ phaseId: nextPhaseId, enteredAt: now });
  return { ...state, phaseId: nextPhaseId, history, updatedAt: now };
}

export function recordBypass(state: ReFeatureState, bypass: Omit<ReFeatureBypass, "phaseId" | "approvedAt" | "approvedBy">): ReFeatureState {
  return {
    ...state,
    bypasses: [
      ...state.bypasses,
      {
        phaseId: state.phaseId,
        approvedAt: Date.now(),
        approvedBy: "user",
        ...bypass,
      },
    ],
    updatedAt: Date.now(),
  };
}

export function applyValidatorArtifacts(state: ReFeatureState, validator: ValidatorResult): ReFeatureState {
  return {
    ...state,
    artifacts: { ...state.artifacts, ...validator.artifacts },
    updatedAt: Date.now(),
  };
}
