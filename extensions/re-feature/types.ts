export const PHASE_IDS = [
  "select_strategy",
  "gather_context",
  "clarify_feature",
  "create_worktree",
  "brainstorm",
  "plan",
  "implement",
  "local_review",
  "compound",
  "address_findings",
  "push_branch",
  "create_pr",
  "pr_verification",
  "merge",
  "update_docs",
  "cleanup",
  "summary",
] as const;

export type PhaseId = (typeof PHASE_IDS)[number];

export type Strictness = "advisory" | "moderate" | "strict";
export type BypassKind = "advance" | "tool_call" | "policy";
export type FindingSeverity = "p1" | "p2" | "p3";
export type FindingStatus = "open" | "fixed" | "deferred" | "accepted";

export interface BashPolicy {
  allowedPatterns?: string[];
  blockedPatterns?: string[];
  requireBypassPatterns?: string[];
  readOnly?: boolean;
}

export interface ArtifactRequirement {
  key: keyof ReFeatureArtifacts;
  description: string;
  required?: boolean;
}

export interface ValidatorResult {
  pass: boolean;
  confidence: "low" | "medium" | "high";
  missing: string[];
  artifacts: Partial<ReFeatureArtifacts>;
  notes: string;
  raw?: string;
}

export interface ReFeatureArtifacts {
  contextSummary?: string;
  brainstormDoc?: string;
  planDoc?: string;
  solutionDoc?: string;
  reviewFindingsPath?: string;
  implementationSummary?: string;
  testsRun?: string;
  pushSummary?: string;
  prSummary?: string;
  prVerificationSummary?: string;
  mergeSummary?: string;
  docsSummary?: string;
  cleanupSummary?: string;
  prNumber?: string;
  prUrl?: string;
  devLogPath?: string;
  adrIds?: string[];
}

export interface ReFeatureFinding {
  id: string;
  severity: FindingSeverity;
  title: string;
  status: FindingStatus;
  sourcePhase: PhaseId;
}

export interface ReFeatureBypass {
  phaseId: PhaseId;
  kind: BypassKind;
  reason: string;
  approvedAt: number;
  approvedBy: "user";
  details?: unknown;
}

export interface ReFeatureHistoryEntry {
  phaseId: PhaseId;
  enteredAt: number;
  exitedAt?: number;
  validator?: ValidatorResult;
  bypassed?: boolean;
}

export interface ReFeatureSourceIssue {
  id: string;
  title: string;
  priority?: string;
  tags?: string[];
}

export interface ReFeaturePreflightChoice {
  selectedAt: number;
  strategyId: string;
  strategyLabel?: string;
  sourceIssue?: ReFeatureSourceIssue;
}

export interface ReFeatureState {
  active: boolean;
  workflowId: string;
  featureDescription: string;
  strategyId: string;
  phaseId: PhaseId;
  cwd: string;
  preflight: ReFeaturePreflightChoice;
  sourceIssue?: ReFeatureSourceIssue;
  worktreePath?: string;
  branchName?: string;
  artifacts: ReFeatureArtifacts;
  findings: ReFeatureFinding[];
  bypasses: ReFeatureBypass[];
  history: ReFeatureHistoryEntry[];
  createdAt: number;
  updatedAt: number;
}

export interface PhaseDefinition {
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
  failureNext?: PhaseId;
  loopWhen?: string;
}

export interface StrategyPhaseOverride {
  enabled?: boolean | "optional";
  guidance?: string;
  tools?: string[];
  allowedWriteGlobs?: string[];
  bashPolicy?: Partial<BashPolicy>;
  exitCriteria?: string[];
}

export interface StrategyDefinition {
  id: string;
  title: string;
  description: string;
  base?: string;
  strictness: Strictness;
  phaseOverrides: Partial<Record<PhaseId, StrategyPhaseOverride>>;
}

export interface ResolvedPhase extends PhaseDefinition {
  enabled: boolean | "optional";
  strategyGuidance?: string;
}
