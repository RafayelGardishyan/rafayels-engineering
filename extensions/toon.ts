import { isToolCallEventType, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { homedir } from "node:os";
import { spawnSync } from "node:child_process";

type CommandAnalysis = {
  tokens: string[];
  operators: string[];
};

type RewriteResult = {
  changed: boolean;
  command: string;
};

type PreprocessorMode = "auto" | "toon" | "rtk" | "off";
function shellQuote(value: string): string {
  return `'${value.replace(/'/g, "'\\''")}'`;
}

function commandExists(command: string): boolean {
  try {
    const result = spawnSync("bash", ["-lc", `command -v ${shellQuote(command)} >/dev/null 2>&1`], {
      stdio: "ignore",
    });
    return result.status === 0;
  } catch {
    return false;
  }
}

function resolveDetectorScript(): string | undefined {
  const candidates = [
    process.env.TOON_DETECT_SCRIPT,
    process.env.TOON_DETECTOR,
    process.env.TOON_PREPROCESS_SCRIPT,
    join(homedir(), ".claude", "hooks", "toon-detect.sh"),
    join(dirname(__dirname), "hooks", "toon-detect.sh"),
  ];

  return candidates.find((candidate): candidate is string => typeof candidate === "string" && existsSync(candidate));
}

function getModeFromEnv(): PreprocessorMode {
  const raw = (process.env.RAFAYELS_TOOL_PREPROCESSOR || process.env.PI_TOOL_PREPROCESSOR || process.env.TOOL_PREPROCESSOR || "auto").toLowerCase();
  if (raw === "toon" || raw === "rtk" || raw === "off") {
    return raw;
  }
  return "auto";
}

function normalizeToken(token: string): string {
  return token.trim().replace(/^['"](.*)['"]$/s, "$1").toLowerCase();
}

function tokenizeTopLevel(command: string): CommandAnalysis {
  const tokens: string[] = [];
  let token = "";

  let inSingleQuote = false;
  let inDoubleQuote = false;
  let inBacktick = false;
  let escaped = false;

  const flushToken = () => {
    if (token.length > 0) {
      tokens.push(token);
      token = "";
    }
  };

  for (let i = 0; i < command.length; i += 1) {
    const char = command[i];

    if (escaped) {
      token += char;
      escaped = false;
      continue;
    }

    if (inSingleQuote) {
      token += char;
      if (char === "'") {
        inSingleQuote = false;
      }
      continue;
    }

    if (inDoubleQuote) {
      token += char;
      if (char === "\\") {
        const next = command[i + 1];
        if (next !== undefined) {
          token += next;
          i += 1;
        }
        continue;
      }
      if (char === '"') {
        inDoubleQuote = false;
      }
      continue;
    }

    if (inBacktick) {
      token += char;
      if (char === "\\") {
        const next = command[i + 1];
        if (next !== undefined) {
          token += next;
          i += 1;
        }
        continue;
      }
      if (char === "`") {
        inBacktick = false;
      }
      continue;
    }

    if (char === "\\") {
      token += char;
      escaped = true;
      continue;
    }

    if (char === "'") {
      inSingleQuote = true;
      token += char;
      continue;
    }

    if (char === '"') {
      inDoubleQuote = true;
      token += char;
      continue;
    }

    if (char === "`") {
      inBacktick = true;
      token += char;
      continue;
    }

    if (char === "#" && (i === 0 || /\s/.test(command[i - 1]))) {
      break;
    }

    if (char === "&" && command[i + 1] === "&") {
      flushToken();
      i += 1;
      continue;
    }

    if (char === "|" && command[i + 1] === "|") {
      flushToken();
      i += 1;
      continue;
    }

    if (char === "|") {
      flushToken();
      continue;
    }

    if (char === ";") {
      flushToken();
      continue;
    }

    if (char === "\n") {
      flushToken();
      continue;
    }

    if (/\s/.test(char)) {
      flushToken();
      continue;
    }

    token += char;
  }

  if (token.length > 0) {
    tokens.push(token);
  }

  return { tokens, operators: [] };
}

function getLeadingCommand(tokens: string[]): string | undefined {
  if (tokens.length === 0) {
    return undefined;
  }
  return normalizeToken(tokens[0]);
}

function isRtkCommandCommand(command: string): boolean {
  const trimmed = command.trim();
  if (!trimmed) return false;
  const analysis = tokenizeTopLevel(trimmed);
  const tokens = analysis.tokens.map(normalizeToken);
  const leading = getLeadingCommand(tokens);
  return leading === "rtk";
}

function getRtkExecutable(): string {
  return process.env.RTK_BIN || "rtk";
}

function rewriteWithRtk(command: string): string | undefined {
  const rtk = getRtkExecutable();
  if (!command.trim()) {
    return undefined;
  }

  if (isRtkCommandCommand(command)) {
    return undefined;
  }

  try {
    const result = spawnSync(rtk, ["rewrite", command], {
      encoding: "utf8",
      maxBuffer: 1024 * 1024 * 20,
    });

    if (result.status !== 0 || result.error) {
      return undefined;
    }

    const rewritten = (result.stdout || "").trim();
    if (!rewritten || rewritten === command.trim()) {
      return undefined;
    }

    return rewritten;
  } catch {
    return undefined;
  }
}

function looksLikeJsonishText(value: string): boolean {
  const trimmed = value.trimStart();
  if (!trimmed) {
    return false;
  }
  const first = trimmed[0];
  return first === "{" || first === "[";
}

function encodeTextViaDetector(text: string, detectorScript: string, toonBin: string): string {
  if (!looksLikeJsonishText(text) || detectorScript.length === 0) {
    return text;
  }

  try {
    const result = spawnSync("bash", [detectorScript], {
      input: text,
      encoding: "utf8",
      maxBuffer: 1024 * 1024 * 50,
      env: {
        ...process.env,
        TOON_BIN: toonBin,
      },
      stdio: "pipe",
    });

    if (result.error || result.status !== 0) {
      return text;
    }

    return (result.stdout || "").replace(/\r\n/g, "\n");
  } catch {
    return text;
  }
}

export default function (pi: ExtensionAPI) {
  const mode: PreprocessorMode = getModeFromEnv();
  const toonBin = process.env.TOON_BIN || "toon";
  const detectorScript = resolveDetectorScript();

  const toonAvailable = Boolean(detectorScript && commandExists(toonBin));
  const rtkAvailable = commandExists(getRtkExecutable());
  const encodeEnabled = mode !== "off" && Boolean(detectorScript && toonAvailable);
  const callIdsForEncoding = new Set<string>();

  const safeRewriteRtk = (command: string): RewriteResult => {
    if (!rtkAvailable) {
      return { changed: false, command };
    }

    const rewritten = rewriteWithRtk(command);
    if (!rewritten) {
      return { changed: false, command };
    }

    return { changed: true, command: rewritten };
  };

  let warned = false;

  pi.on("tool_call", (event, ctx) => {
    if (!isToolCallEventType("bash", event)) {
      return;
    }

    if (mode === "off") {
      return;
    }

    const originalCommand = event.input.command;

    if (!originalCommand || typeof originalCommand !== "string") {
      return;
    }

    let rewritten: RewriteResult | undefined;

    if (mode !== "toon") {
      rewritten = safeRewriteRtk(originalCommand);
      if (rewritten.changed) {
        event.input.command = rewritten.command;
      }
    }

    if (encodeEnabled) {
      callIdsForEncoding.add(event.toolCallId);
    }

    if (!rewritten?.changed && !warned && mode !== "off") {
      let reason: string | undefined;
      if (mode === "rtk" && !rtkAvailable) {
        reason = `rtk binary not available (${getRtkExecutable()})`;
      } else if (mode === "toon" && !toonAvailable) {
        reason = `toon binary or detector script not available`;
      } else if (mode === "auto" && !rtkAvailable) {
        reason = `rtk not available, falling back to raw command with Toon encoding${toonAvailable ? "" : " (Toon unavailable)"}`;
      }

      if (reason && (mode !== "auto" || !rtkAvailable)) {
        ctx.ui.notify(`Tool preprocessor disabled for this command: ${reason}`, "warning");
        warned = true;
      }
    }

    return;
  });

  pi.on("tool_result", (event) => {
    if (!callIdsForEncoding.has(event.toolCallId) || !detectorScript) {
      callIdsForEncoding.delete(event.toolCallId);
      return;
    }

    let changed = false;
    const nextContent = event.content.map((entry) => {
      if (entry.type !== "text") {
        return entry;
      }

      const encoded = encodeTextViaDetector(entry.text, detectorScript, toonBin);
      if (encoded !== entry.text) {
        changed = true;
      }

      return encoded === entry.text
        ? entry
        : {
            type: "text",
            text: encoded,
          };
    });

    callIdsForEncoding.delete(event.toolCallId);

    if (changed) {
      return { content: nextContent };
    }
  });
}
