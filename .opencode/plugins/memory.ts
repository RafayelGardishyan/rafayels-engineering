import type { Plugin } from "@opencode-ai/plugin"

const PLUGIN_BASE = `${process.env.HOME}/.claude/plugins/cache/rafayels-marketplace/rafayels-engineering`

function resolveMemoryScript(): string | null {
  try {
    const dirs = Array.from(new Bun.Glob(`${PLUGIN_BASE}/*/`).scanSync())
    if (dirs.length === 0) return null
    dirs.sort()
    const latest = dirs[dirs.length - 1]
    const mem = `${latest}skills/memory/scripts/memory`
    if (Bun.file(mem).size > 0) return mem
    return null
  } catch {
    return null
  }
}

function mapSkillToPhase(skill: string): string | null {
  switch (skill) {
    case "workflows:brainstorm":
    case "rafayels-engineering:workflows:brainstorm":
      return "brainstorm"
    case "workflows:plan":
    case "rafayels-engineering:workflows:plan":
      return "plan"
    case "workflows:work":
    case "rafayels-engineering:workflows:work":
      return "work"
    case "workflows:review":
    case "rafayels-engineering:workflows:review":
      return "review"
    case "workflows:compound":
    case "rafayels-engineering:workflows:compound":
      return "compound"
    default:
      return null
  }
}

function truncate(str: string, maxLen: number): string {
  return str.length > maxLen ? str.slice(0, maxLen) : str
}

export const MemoryPlugin: Plugin = async ({ client }) => {
  const MEM = resolveMemoryScript()

  if (!MEM) {
    await client.app.log({
      body: { service: "memory-plugin", level: "warn", message: "Memory script not found" },
    })
  }

  return {
    "tool.execute.before": async (input, output) => {
      if (!MEM || input.tool !== "skill") return

      const skill = output.args?.skill ?? ""
      const phase = mapSkillToPhase(skill)
      if (!phase) return

      const query = truncate(String(output.args?.args ?? ""), 500)
      if (!query) return

      try {
        const proc = Bun.spawn([MEM, "query", query, "--phase", phase, "--k", "3", "--format", "md"], {
          stdout: "pipe",
          stderr: "pipe",
        })
        const cases = await new Response(proc.stdout).text()
        if (cases.trim()) {
          const prefix = `[Memory Layer] Retrieved relevant cases for ${phase} phase:\n\n${cases}\n\n---\n\n`
          output.args.args = prefix + String(output.args.args ?? "")
        }
      } catch {
        // Graceful degradation
      }
    },

    "tool.execute.after": async (input, output) => {
      if (!MEM || input.tool !== "skill") return

      const skill = input.args?.skill ?? ""
      const phase = mapSkillToPhase(skill)
      if (!phase) return

      const query = truncate(String(input.args?.args ?? ""), 500)
      if (!query) return

      const type = phase === "brainstorm" ? "decision" : phase === "review" ? "pattern" : "solution"
      const title = truncate(`${phase} phase: ${query}`, 150)

      try {
        // Write case
        const writeProc = Bun.spawn(
          [MEM, "--json", "write", "--phase", phase, "--type", type, "--title", title, "--query", query, "--tags", `["${phase}","auto-captured"]`],
          { stdout: "pipe", stderr: "pipe" }
        )
        const writeResult = await new Response(writeProc.stdout).text()
        if (!writeResult.trim()) return

        let caseId: string | null = null
        try {
          const parsed = JSON.parse(writeResult)
          caseId = parsed.case_id ?? null
        } catch {
          return
        }

        if (caseId) {
          // Emit approval signal (fire-and-forget)
          Bun.spawn(
            [MEM, "signal", String(caseId), "approval", "1.0", "--source", "hook:post-skill"],
            { stdout: "ignore", stderr: "ignore" }
          )
        }
      } catch {
        // Graceful degradation
      }
    },
  }
}
