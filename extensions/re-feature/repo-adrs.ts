import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, relative } from "node:path";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

type AdrBackend = { location: "mcp" | "repo"; repoDir?: string; error?: string };
type RepoAdr = { id: string; title: string; path: string; content: string };

async function getConfig(pi: ExtensionAPI, cwd: string, key: string): Promise<string | undefined> {
  const candidates = [
    join(__dirname, "../../skills/project-config/scripts/cli.py"),
    join(cwd, "skills/project-config/scripts/cli.py"),
  ];
  const script = candidates.find((candidate) => existsSync(candidate)) ?? candidates[0];
  const python = process.env.PYTHON_FOR_RAFAYELS_ENGINEERING || "python3";
  const result = await pi.exec(python, [script, "get", key, "--json"], { timeout: 5000 });
  if (result.code !== 0) return undefined;
  try {
    const parsed = JSON.parse(result.stdout);
    if (typeof parsed === "string") return parsed;
    if (typeof parsed?.value === "string") return parsed.value;
    if (typeof parsed?.config?.[key] === "string") return parsed.config[key];
  } catch {
    const trimmed = result.stdout.trim();
    return trimmed || undefined;
  }
  return undefined;
}

export async function resolveAdrBackend(pi: ExtensionAPI, cwd: string): Promise<AdrBackend> {
  const location = await getConfig(pi, cwd, "adr.location");
  if (location !== "repo") return { location: "mcp" };
  const repoDir = await getConfig(pi, cwd, "adr.repo_dir");
  if (!repoDir) return { location: "repo", error: "adr.location=repo but adr.repo_dir is not configured" };
  return { location: "repo", repoDir };
}

function walkMarkdown(dir: string, limit = 300): string[] {
  if (!existsSync(dir)) return [];
  const out: string[] = [];
  const walk = (current: string) => {
    if (out.length >= limit) return;
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      if (entry.name.startsWith(".")) continue;
      const full = join(current, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.isFile() && /\.mdx?$/i.test(entry.name)) out.push(full);
      if (out.length >= limit) return;
    }
  };
  walk(dir);
  return out;
}

function parseTitle(content: string, filePath: string): string {
  const heading = content.match(/^#\s+(.+)$/m)?.[1]?.trim();
  if (heading) return heading;
  return basename(filePath).replace(/\.mdx?$/i, "");
}

function parseId(content: string, filePath: string): string {
  const frontmatterId = content.match(/^---[\s\S]*?\n(?:id|adr_id):\s*['"]?([^'"\n]+)['"]?\s*\n[\s\S]*?---/i)?.[1]?.trim();
  if (frontmatterId) return frontmatterId;
  const name = basename(filePath).replace(/\.mdx?$/i, "");
  return name.match(/^(ADR[-_ ]?\d+|\d+)/i)?.[1]?.replace(/[_ ]/g, "-") ?? name;
}

export function loadRepoAdrs(cwd: string, repoDir: string): RepoAdr[] {
  const files = walkMarkdown(repoDir);
  return files.map((file) => {
    const content = readFileSync(file, "utf8");
    return { id: parseId(content, file), title: parseTitle(content, file), path: relative(cwd, file), content };
  });
}

function scoreAdr(adr: RepoAdr, query: string): number {
  const terms = query.toLowerCase().split(/\W+/).filter((term) => term.length > 2);
  const haystack = `${adr.id} ${adr.title} ${adr.content}`.toLowerCase();
  return terms.reduce((score, term) => score + (haystack.includes(term) ? 1 : 0), 0);
}

export function searchRepoAdrs(cwd: string, repoDir: string, query: string, limit = 8) {
  return loadRepoAdrs(cwd, repoDir)
    .map((adr) => ({ ...adr, score: scoreAdr(adr, query) }))
    .filter((adr) => adr.score > 0)
    .sort((a, b) => b.score - a.score || a.id.localeCompare(b.id))
    .slice(0, limit)
    .map((adr) => ({ id: adr.id, title: adr.title, path: adr.path, score: adr.score }));
}

export function getRepoAdr(cwd: string, repoDir: string, idOrPath: string): RepoAdr | undefined {
  const adrs = loadRepoAdrs(cwd, repoDir);
  return adrs.find((adr) => adr.id === idOrPath || adr.path === idOrPath || basename(adr.path) === idOrPath);
}

export function listRepoAdrs(cwd: string, repoDir: string) {
  return loadRepoAdrs(cwd, repoDir).map((adr) => ({ id: adr.id, title: adr.title, path: adr.path }));
}

export function repoAdrDirExists(repoDir: string): boolean {
  try {
    return statSync(repoDir).isDirectory();
  } catch {
    return false;
  }
}
