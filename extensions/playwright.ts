import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";

export default function (pi: ExtensionAPI) {
  async function run(command: string, signal?: AbortSignal) {
    const result = await pi.exec("bash", ["-lc", command], { signal });
    if (result.code !== 0) {
      throw new Error(result.stderr || result.stdout || `agent-browser failed with exit code ${result.code}`);
    }
    return {
      content: [{ type: "text", text: result.stdout.trim() || "OK" }],
      details: { code: result.code, stdout: result.stdout, stderr: result.stderr },
    };
  }

  function registerNavigateTool(name: string, description: string) {
    pi.registerTool({
      name,
      label: "Browser Navigate",
      description,
      parameters: Type.Object({
        url: Type.String({ description: "URL to open in the browser" }),
      }),
      async execute(_toolCallId, params, signal) {
        return run(`agent-browser open ${JSON.stringify(params.url)}`, signal);
      },
    });
  }

  function registerSnapshotTool(name: string, description: string) {
    pi.registerTool({
      name,
      label: "Browser Snapshot",
      description,
      parameters: Type.Object({
        interactiveOnly: Type.Optional(Type.Boolean({ description: "Only include interactive elements" })),
        json: Type.Optional(Type.Boolean({ description: "Return JSON output" })),
      }),
      async execute(_toolCallId, params, signal) {
        const flags = [
          params.interactiveOnly === false ? "" : "-i",
          params.json ? "--json" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return run(`agent-browser snapshot ${flags}`.trim(), signal);
      },
    });
  }

  function registerScreenshotTool(name: string, description: string) {
    pi.registerTool({
      name,
      label: "Browser Screenshot",
      description,
      parameters: Type.Object({
        filename: Type.String({ description: "Output path for the screenshot" }),
        fullPage: Type.Optional(Type.Boolean({ description: "Capture the full page" })),
      }),
      async execute(_toolCallId, params, signal) {
        const full = params.fullPage ? "--full " : "";
        return run(`agent-browser screenshot ${full}${JSON.stringify(params.filename)}`, signal);
      },
    });
  }

  function registerConsoleTool(name: string, description: string) {
    pi.registerTool({
      name,
      label: "Browser Console",
      description,
      parameters: Type.Object({
        level: Type.Optional(Type.String({ description: "Optional console level filter" })),
      }),
      async execute(_toolCallId, params, signal) {
        const suffix = params.level ? ` | grep -i ${JSON.stringify(params.level)}` : "";
        return run(`agent-browser logs${suffix}`, signal);
      },
    });
  }

  function registerClickTool(name: string, description: string) {
    pi.registerTool({
      name,
      label: "Browser Click",
      description,
      parameters: Type.Object({
        ref: Type.String({ description: "Element ref such as @e1 from snapshot output" }),
      }),
      async execute(_toolCallId, params, signal) {
        return run(`agent-browser click ${JSON.stringify(params.ref)}`, signal);
      },
    });
  }

  function registerTypeTool(name: string, description: string, mode: "type" | "fill") {
    pi.registerTool({
      name,
      label: mode === "fill" ? "Browser Fill" : "Browser Type",
      description,
      parameters: Type.Object({
        ref: Type.String({ description: "Element ref such as @e1 from snapshot output" }),
        text: Type.String({ description: "Text to send to the element" }),
      }),
      async execute(_toolCallId, params, signal) {
        return run(`agent-browser ${mode} ${JSON.stringify(params.ref)} ${JSON.stringify(params.text)}`, signal);
      },
    });
  }

  registerNavigateTool("browser_navigate", "Navigate to a URL using the native Pi browser bridge.");
  registerNavigateTool(
    "mcp__plugin_compound-engineering_pw__browser_navigate",
    "Claude/OpenCode compatibility alias for browser_navigate.",
  );

  registerSnapshotTool("browser_snapshot", "Get a snapshot of the current page DOM/accessibility tree.");
  registerSnapshotTool(
    "mcp__plugin_compound-engineering_pw__browser_snapshot",
    "Claude/OpenCode compatibility alias for browser_snapshot.",
  );

  registerScreenshotTool("browser_take_screenshot", "Take a screenshot of the current page.");
  registerScreenshotTool(
    "mcp__plugin_compound-engineering_pw__browser_take_screenshot",
    "Claude/OpenCode compatibility alias for browser_take_screenshot.",
  );

  registerConsoleTool("browser_console_messages", "Get console messages from the current browser session.");
  registerConsoleTool(
    "mcp__plugin_compound-engineering_pw__browser_console_messages",
    "Claude/OpenCode compatibility alias for browser_console_messages.",
  );

  registerClickTool("browser_click", "Click an element by snapshot ref.");
  registerTypeTool("browser_type", "Type text into an element by snapshot ref.", "type");
  registerTypeTool("browser_fill", "Clear and fill an input by snapshot ref.", "fill");
}
