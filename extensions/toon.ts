import { isToolCallEventType, type ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync } from "node:fs";
import { basename, dirname, join } from "node:path";
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
type Strategy = "toon" | "rtk";

const BLOCKED_TOOL_NAMES = new Set([
  "toon",
  "rtk",
  "toon-detect",
  "toon-detect.sh",
  "toon-preprocessor",
  "toon-preprocessor.sh",
]);

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

function isAssignmentToken(token: string): boolean {
  return /^[A-Za-z_][A-Za-z0-9_]*=.*/.test(token);
}

function tokenizeTopLevel(command: string): CommandAnalysis {
  const operators: string[] = [];
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
      operators.push("&&");
      i += 1;
      continue;
    }

    if (char === "|" && command[i + 1] === "|") {
      flushToken();
      operators.push("||");
      i += 1;
      continue;
    }

    if (char === "|") {
      flushToken();
      operators.push("|");
      continue;
    }

    if (char === ";") {
      flushToken();
      operators.push(";");
      continue;
    }

    if (char === "\n") {
      flushToken();
      operators.push("\n");
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

  return { tokens, operators };
}

function getLeadingCommand(tokens: string[]): string | undefined {
  let index = 0;
  while (index < tokens.length && isAssignmentToken(tokens[index])) {
    index += 1;
  }
  if (index >= tokens.length) {
    return undefined;
  }
  return normalizeToken(tokens[index]);
}

function containsBlockedToonUsage(tokens: string[]): boolean {
  return tokens.some((token) => {
    const normalized = normalizeToken(token);
    if (BLOCKED_TOOL_NAMES.has(normalized)) {
      return true;
    }

    const base = basename(normalized);
    return BLOCKED_TOOL_NAMES.has(base);
  });
}

function isRtkCommandCommand(command: string): boolean {
  const trimmed = command.trim();
  if (!trimmed) return false;
  const analysis = tokenizeTopLevel(trimmed);
  const tokens = analysis.tokens.map(normalizeToken);
  const leading = getLeadingCommand(tokens);
  return leading === "rtk";
}

function shouldRewriteToonCommand(command: string): boolean {
  const trimmed = command.trim();
  if (!trimmed) {
    return false;
  }

  const analysis = tokenizeTopLevel(trimmed);

  if (
    analysis.operators.includes("&&") ||
    analysis.operators.includes("||") ||
    analysis.operators.includes("|") ||
    analysis.operators.includes(";") ||
    analysis.operators.includes("\n")
  ) {
    return false;
  }

  const tokens = analysis.tokens.map(normalizeToken);

  const leading = getLeadingCommand(tokens);
  if (!leading) {
    return false;
  }

  if (leading === "toon" || leading === "rtk") {
    return false;
  }

  if (containsBlockedToonUsage(tokens)) {
    return false;
  }

  return true;
}

function rewriteWithToon(command: string, toonBin: string, detectorScript: string): string {
  return `set -o pipefail; ${command} | TOON_BIN=${shellQuote(toonBin)} bash ${shellQuote(detectorScript)}`;
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
  const callStrategy = new Map<string, Strategy>();

  let warned = false;

  const safeRewriteToon = (command: string): RewriteResult => {
    if (!toonAvailable || !shouldRewriteToonCommand(command) || !detectorScript) {
      return { changed: false, command };
    }

    return {
      changed: true,
      command: rewriteWithToon(command, toonBin, detectorScript),
    };
  };

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

    if (mode === "toon") {
      rewritten = safeRewriteToon(originalCommand);
      if (rewritten.changed) {
        callStrategy.set(event.toolCallId, "toon");
      }
    } else if (mode === "rtk") {
      rewritten = safeRewriteRtk(originalCommand);
      if (rewritten.changed) {
        callStrategy.set(event.toolCallId, "rtk");
      }
    } else {
      // Auto: prefer RTK rewrites first, then fallback to Toon when safe.
      rewritten = safeRewriteRtk(originalCommand);
      if (rewritten.changed) {
        callStrategy.set(event.toolCallId, "rtk");
      } else {
        rewritten = safeRewriteToon(originalCommand);
        if (rewritten.changed) {
          callStrategy.set(event.toolCallId, "toon");
        }
      }
    }

    if (!rewritten?.changed && !warned && mode !== "off") {
      let reason: string | undefined;
      if (mode === "rtk" && !rtkAvailable) {
        reason = `rtk binary not available (${getRtkExecutable()})`;
      } else if (mode === "toon" && !toonAvailable) {
        reason = `toon binary or detector script not available`;
      } else if (mode === "auto" && !rtkAvailable && !toonAvailable) {
        reason = `no Toon or RTK preprocessor available`;
      }

      if (reason) {
        ctx.ui.notify(`Tool preprocessor disabled for this command: ${reason}`, "warning");
        warned = true;
      }
    }

    if (rewritten?.changed) {
      event.input.command = rewritten.command;
      return;
    }

    return;
  });

  pi.on("tool_result", (event) => {
    const strategy = callStrategy.get(event.toolCallId);

    if (!strategy) {
      return;
    }

    // Keep RTK outputs untouched; they are already preprocessed.
    if (strategy === "rtk") {
      callStrategy.delete(event.toolCallId);
      return;
    }

    if (strategy !== "toon" || !detectorScript) {
      callStrategy.delete(event.toolCallId);
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

    callStrategy.delete(event.toolCallId);

    if (changed) {
      return { content: nextContent };
    }
  });
}
