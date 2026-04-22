import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { Type } from "@sinclair/typebox";
import { existsSync } from "node:fs";
import { join } from "node:path";

export default function (pi: ExtensionAPI) {
  const possiblePaths = [
    join(__dirname, "../skills/project-config/scripts/cli.py"),
    join(process.cwd(), "skills/project-config/scripts/cli.py"),
  ];

  const scriptPath = possiblePaths.find((path) => existsSync(path)) ?? possiblePaths[0];
  const pythonCmd = process.env.PYTHON_FOR_RAFAYELS_ENGINEERING || "python3";

  async function run(args: string[], signal?: AbortSignal) {
    const result = await pi.exec(pythonCmd, [scriptPath, ...args], { signal });
    if (result.code !== 0) {
      throw new Error(result.stderr || result.stdout || `project-config failed with exit code ${result.code}`);
    }
    return {
      content: [{ type: "text", text: result.stdout.trim() || "OK" }],
      details: { code: result.code, stdout: result.stdout, stderr: result.stderr },
    };
  }

  pi.registerTool({
    name: "get_config_value",
    label: "Get Config Value",
    description: "Return one resolved config value from the project. Key is dotted (e.g. 'vault.path').",
    parameters: Type.Object({
      key: Type.String({ description: "Dotted key name" })
    }),
    async execute(_toolCallId, params, signal) {
      return run(["get", params.key, "--json"], signal);
    }
  });

  pi.registerTool({
    name: "get_all_config",
    label: "Get All Config",
    description: "Return every resolved config key with its value and source layer.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, signal) {
      return run(["list", "--json"], signal);
    }
  });

  pi.registerTool({
    name: "get_config_source",
    label: "Get Config Source",
    description: "Return which layer (team/local/env/default) supplied a key's value.",
    parameters: Type.Object({
      key: Type.String()
    }),
    async execute(_toolCallId, params, signal) {
      return run(["where", params.key], signal);
    }
  });

  pi.registerTool({
    name: "list_config_keys",
    label: "List Config Keys",
    description: "Return all known config keys.",
    parameters: Type.Object({}),
    async execute(_toolCallId, _params, signal) {
      return run(["keys"], signal);
    }
  });

  pi.registerTool({
    name: "init_config",
    label: "Init Config",
    description: "Initialize the project configuration.",
    parameters: Type.Object({
      values: Type.Record(Type.String(), Type.String(), { description: "Dictionary of key=value pairs" }),
      force: Type.Optional(Type.Boolean())
    }),
    async execute(_toolCallId, params, signal) {
      const args = ["init", "--non-interactive"];
      if (params.force) args.push("--force");

      for (const [key, value] of Object.entries(params.values)) {
        args.push("--set", `${key}=${value}`);
      }

      return run(args, signal);
    }
  });
}
