import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { tmpdir } from "node:os";

type PromptAlias = {
  alias: string;
  target: string;
  raw: string;
};

let generatedPromptDir: string | undefined;

function parsePromptAlias(filePath: string): PromptAlias | null {
  const raw = readFileSync(filePath, "utf-8");
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?[\s\S]*$/);

  if (!match) {
    return null;
  }

  let alias: string | undefined;

  for (const line of match[1].split(/\r?\n/)) {
    const separatorIndex = line.indexOf(":");
    if (separatorIndex === -1) {
      continue;
    }

    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim().replace(/^(["'])(.*)\1$/s, "$2");

    if (key === "name") {
      alias = value;
      break;
    }
  }

  if (!alias) {
    return null;
  }

  const target = basename(filePath, ".md");
  if (alias === target) {
    return null;
  }

  return { alias, target, raw };
}

function walkMarkdownFiles(dir: string): string[] {
  if (!existsSync(dir)) {
    return [];
  }

  const files: string[] = [];

  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) {
      continue;
    }

    const fullPath = join(dir, entry.name);

    let isDirectory = entry.isDirectory();
    let isFile = entry.isFile();

    if (entry.isSymbolicLink()) {
      try {
        const stats = statSync(fullPath);
        isDirectory = stats.isDirectory();
        isFile = stats.isFile();
      } catch {
        continue;
      }
    }

    if (isDirectory) {
      files.push(...walkMarkdownFiles(fullPath));
    } else if (isFile && entry.name.endsWith(".md")) {
      files.push(fullPath);
    }
  }

  return files;
}

function collectPromptAliases(commandsDir: string): PromptAlias[] {
  const aliases = new Map<string, PromptAlias>();

  for (const filePath of walkMarkdownFiles(commandsDir)) {
    const alias = parsePromptAlias(filePath);
    if (!alias || aliases.has(alias.alias)) {
      continue;
    }
    aliases.set(alias.alias, alias);
  }

  return Array.from(aliases.values()).sort((a, b) => a.alias.localeCompare(b.alias));
}

function ensureGeneratedPromptDir(aliases: PromptAlias[]): string | undefined {
  if (generatedPromptDir && existsSync(generatedPromptDir)) {
    return generatedPromptDir;
  }

  try {
    const root = mkdtempSync(join(tmpdir(), "rafayels-pi-command-aliases-"));
    const promptsDir = join(root, "prompts");
    mkdirSync(promptsDir, { recursive: true });

    for (const alias of aliases) {
      if (alias.alias.includes("/") || alias.alias.includes("\\")) {
        continue;
      }
      writeFileSync(join(promptsDir, `${alias.alias}.md`), alias.raw, "utf-8");
    }

    generatedPromptDir = promptsDir;
    return generatedPromptDir;
  } catch {
    return undefined;
  }
}

function rewriteAliasInput(text: string, aliasesByName: Map<string, string>): string {
  if (!text.startsWith("/")) {
    return text;
  }

  const spaceIndex = text.indexOf(" ");
  const commandName = spaceIndex === -1 ? text.slice(1) : text.slice(1, spaceIndex);
  const target = aliasesByName.get(commandName);

  if (!target) {
    return text;
  }

  const args = spaceIndex === -1 ? "" : text.slice(spaceIndex + 1);
  return args ? `/${target} ${args}` : `/${target}`;
}

export default function (pi: ExtensionAPI) {
  const commandsDir = join(dirname(__dirname), "commands");
  const aliases = collectPromptAliases(commandsDir);
  const aliasesByName = new Map(aliases.map((alias) => [alias.alias, alias.target]));

  pi.on("input", (event) => {
    const rewritten = rewriteAliasInput(event.text, aliasesByName);
    if (rewritten === event.text) {
      return { action: "continue" };
    }

    return {
      action: "transform",
      text: rewritten,
      images: event.images,
    };
  });

  pi.on("resources_discover", () => {
    const promptDir = ensureGeneratedPromptDir(aliases);
    if (!promptDir) {
      return {};
    }

    return {
      promptPaths: [promptDir],
    };
  });
}
