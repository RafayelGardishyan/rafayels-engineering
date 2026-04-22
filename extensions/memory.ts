import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { existsSync } from "node:fs";
import { join } from "node:path";

export default function (pi: ExtensionAPI) {
  const possiblePaths = [
    join(__dirname, "../skills/memory/scripts/memory.py"),
    join(process.cwd(), "skills/memory/scripts/memory.py"),
  ];

  const scriptPath = possiblePaths.find((path) => existsSync(path)) ?? possiblePaths[0];
  const pythonCmd = process.env.PYTHON_FOR_RAFAYELS_ENGINEERING || "python3";

  async function run(args: string[], signal?: AbortSignal) {
    const result = await pi.exec(pythonCmd, [scriptPath, ...args], { signal });
    if (result.code !== 0) {
      throw new Error(result.stderr || result.stdout || `memory tool failed with exit code ${result.code}`);
    }
    return {
      content: [{ type: "text", text: result.stdout.trim() || "OK" }],
      details: { code: result.code, stdout: result.stdout, stderr: result.stderr },
    };
  }

  pi.registerTool({
    name: "memory_write",
    label: "Memory Write",
    description: "Write a new case to the persistent memory bank.",
    promptSnippet: "Record a learned pattern or successful outcome into the memory bank.",
    promptGuidelines: ["Use memory_write when you've successfully solved a complex problem to save the pattern for the future."],
    parameters: Type.Object({
      phase: Type.String({ description: "Workflow phase (e.g., brainstorm, plan, work, review, compound)" }),
      query: Type.String({ description: "The problem or task description" }),
      plan: Type.Optional(Type.String({ description: "The plan or approach used" })),
      outcome: Type.Optional(Type.String({ description: "The final result or learning" })),
      tags: Type.Optional(Type.Array(Type.String(), { description: "List of tags" }))
    }),
    async execute(_toolCallId, params, signal) {
      const args = ["--json", "write", "--phase", params.phase, "--query", params.query];

      if (params.plan) args.push("--plan", params.plan);
      if (params.outcome) args.push("--outcome", params.outcome);
      if (params.tags && params.tags.length > 0) args.push("--tags", JSON.stringify(params.tags));

      return run(args, signal);
    }
  });

  pi.registerTool({
    name: "memory_query",
    label: "Memory Query",
    description: "Retrieve relevant past cases from the persistent memory bank based on a semantic query.",
    promptSnippet: "Search the memory bank for past cases, patterns, and solutions.",
    promptGuidelines: ["Use memory_query to check how similar problems were solved in the past."],
    parameters: Type.Object({
      query: Type.String({ description: "The text to search for" }),
      phase: Type.Optional(Type.String({ description: "Filter by workflow phase" })),
      k: Type.Optional(Type.Number({ description: "Number of results to return (default: 3)" }))
    }),
    async execute(_toolCallId, params, signal) {
      const args = ["--json", "query", params.query];

      if (params.phase) args.push("--phase", params.phase);
      args.push("--k", params.k !== undefined ? params.k.toString() : "3");
      args.push("--format", "md");

      return run(args, signal);
    }
  });

  pi.registerTool({
    name: "memory_signal",
    label: "Memory Signal",
    description: "Append a signal to an existing memory case.",
    promptSnippet: "Promote or demote a memory case by sending a signal.",
    parameters: Type.Object({
      id: Type.Number({ description: "The case ID" }),
      type: Type.String({ description: "Signal type (merge, ci, approval, review, regression)" }),
      value: Type.Number({ description: "Signal weight (e.g., 1.0 for positive, -1.0 for negative)" }),
      source: Type.Optional(Type.String({ description: "Source of the signal (e.g., pr:#123)" }))
    }),
    async execute(_toolCallId, params, signal) {
      const args = ["--json", "signal", params.id.toString(), params.type, params.value.toString()];
      if (params.source) args.push("--source", params.source);

      return run(args, signal);
    }
  });

  // Inject memory context based on active workflow skills
  pi.on("before_agent_start", async (event, ctx) => {
    // Look at the active skills in systemPromptOptions
    const activeSkills = event.systemPromptOptions.skills || [];
    let phase = "";
    let query = event.prompt.substring(0, 500); // Truncate the prompt to use as the query
    
    for (const skill of activeSkills) {
      const name = skill.name;
      if (name.includes("brainstorm")) phase = "brainstorm";
      else if (name.includes("plan")) phase = "plan";
      else if (name.includes("work")) phase = "work";
      else if (name.includes("review")) phase = "review";
      else if (name.includes("compound")) phase = "compound";
      
      if (phase) break;
    }
    
    if (phase) {
      // Run query automatically
      const args = ["query", query, "--phase", phase, "--k", "3", "--format", "md"];
      const result = await pi.exec(pythonCmd, [scriptPath, ...args], { signal: ctx.signal });

      if (result.code === 0 && result.stdout.trim() !== "") {
        return {
          systemPrompt:
            event.systemPrompt +
            "\n\n[Memory Layer] Retrieved relevant cases for " +
            phase +
            " phase:\n\n" +
            result.stdout,
        };
      }
    }
  });
}
