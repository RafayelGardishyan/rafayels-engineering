import { spawn } from "node:child_process";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import type { ResolvedPhase, ReFeatureState, ValidatorResult } from "./types.js";

function extractJson(text: string): unknown {
  const trimmed = text.trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    const match = trimmed.match(/\{[\s\S]*\}/);
    if (!match) throw new Error("No JSON object found");
    return JSON.parse(match[0]);
  }
}

function normalizeValidatorResult(value: any, raw: string): ValidatorResult {
  return {
    pass: Boolean(value?.pass),
    confidence: value?.confidence === "high" || value?.confidence === "medium" || value?.confidence === "low" ? value.confidence : "low",
    missing: Array.isArray(value?.missing) ? value.missing.map(String) : [],
    artifacts: typeof value?.artifacts === "object" && value.artifacts ? value.artifacts : {},
    notes: typeof value?.notes === "string" ? value.notes : "",
    raw,
  };
}

function finalAssistantTextFromJsonEvents(stdout: string): string {
  let finalText = "";
  for (const line of stdout.split(/\r?\n/)) {
    if (!line.trim()) continue;
    try {
      const event = JSON.parse(line);
      const message = event?.message;
      if (event?.type === "message_end" && message?.role === "assistant" && Array.isArray(message.content)) {
        const text = message.content.find((part: any) => part?.type === "text")?.text;
        if (typeof text === "string") finalText = text;
      }
    } catch {
      // ignore non-json progress lines
    }
  }
  return finalText || stdout;
}

export async function runValidator(args: {
  cwd: string;
  phase: ResolvedPhase;
  state: ReFeatureState;
  evidence: string;
  signal?: AbortSignal;
}): Promise<ValidatorResult> {
  const tempDir = await mkdtemp(join(tmpdir(), "re-feature-validator-"));
  const systemPromptPath = join(tempDir, "system.md");
  const systemPrompt = `You are a fast, skeptical validator for Rafayel Engineering's enforced /re-feature workflow.\n\nReturn ONLY strict JSON with this shape:\n{\n  "pass": boolean,\n  "confidence": "low" | "medium" | "high",\n  "missing": string[],\n  "artifacts": object,\n  "notes": string\n}\n\nUse read-only inspection. Do not modify files. Do not trust agent claims without checking when possible.`;
  await writeFile(systemPromptPath, systemPrompt, "utf8");

  const task = `Validate current /re-feature phase completion.\n\nPhase: ${args.phase.id} (${args.phase.title})\nObjective: ${args.phase.objective}\nStrategy: ${args.state.strategyId}\nFeature: ${args.state.featureDescription}\nSource issue: ${args.state.sourceIssue ? `${args.state.sourceIssue.id} ${args.state.sourceIssue.title}` : "none"}\n\nExit criteria:\n${args.phase.exitCriteria.map((criterion) => `- ${criterion}`).join("\n")}\n\nRequired artifacts:\n${args.phase.requiredArtifacts.map((artifact) => `- ${artifact.key}: ${artifact.description}`).join("\n") || "- none"}\n\nAgent evidence:\n${args.evidence}\n\nAdditional validator instructions:\n${args.phase.validatorPrompt}`;

  const invocation = ["--mode", "json", "-p", "--no-session", "--tools", "read,bash", "--append-system-prompt", systemPromptPath, task];

  try {
    const result = await new Promise<{ code: number; stdout: string; stderr: string }>((resolve) => {
      const proc = spawn("pi", invocation, { cwd: args.cwd, stdio: ["ignore", "pipe", "pipe"] });
      let stdout = "";
      let stderr = "";
      proc.stdout.on("data", (data) => (stdout += data.toString()));
      proc.stderr.on("data", (data) => (stderr += data.toString()));
      proc.on("close", (code) => resolve({ code: code ?? 0, stdout, stderr }));
      proc.on("error", (error) => resolve({ code: 1, stdout, stderr: String(error) }));
      if (args.signal) {
        const kill = () => proc.kill("SIGTERM");
        if (args.signal.aborted) kill();
        else args.signal.addEventListener("abort", kill, { once: true });
      }
    });

    if (result.code !== 0) {
      return {
        pass: false,
        confidence: "low",
        missing: [`Validator process failed: ${result.stderr || `exit ${result.code}`}`],
        artifacts: {},
        notes: "Validator failed closed.",
        raw: result.stdout,
      };
    }

    const text = finalAssistantTextFromJsonEvents(result.stdout);
    return normalizeValidatorResult(extractJson(text), text);
  } catch (error) {
    return {
      pass: false,
      confidence: "low",
      missing: [`Validator returned malformed output: ${error instanceof Error ? error.message : String(error)}`],
      artifacts: {},
      notes: "Validator failed closed.",
    };
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}
