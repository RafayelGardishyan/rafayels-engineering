import { Type } from "@mariozechner/pi-ai";
import type { ExtensionAPI, ExtensionCommandContext, Theme } from "@mariozechner/pi-coding-agent";
import { defineTool } from "@mariozechner/pi-coding-agent";
import { existsSync } from "node:fs";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { matchesKey, visibleWidth, type Focusable } from "@mariozechner/pi-tui";

type IssueStatus = "open" | "closed";
type IssuePriority = "p1" | "p2" | "p3";

type IssueNote = {
  created_at: string;
  text: string;
};

type IssueRecord = {
  id: string;
  title: string;
  status: IssueStatus;
  priority: IssuePriority;
  tags: string[];
  created_at: string;
  updated_at: string;
  notes: IssueNote[];
};

function nowIso() {
  return new Date().toISOString();
}

function issuesDir(cwd: string) {
  return join(cwd, ".pi", "issues");
}

function issuePath(cwd: string, id: string) {
  return join(issuesDir(cwd), `${id}.json`);
}

async function ensureIssuesDir(cwd: string) {
  await mkdir(issuesDir(cwd), { recursive: true });
}

async function readIssue(cwd: string, id: string): Promise<IssueRecord | null> {
  try {
    const raw = await readFile(issuePath(cwd, id), "utf8");
    return JSON.parse(raw) as IssueRecord;
  } catch {
    return null;
  }
}

async function writeIssue(cwd: string, issue: IssueRecord) {
  await ensureIssuesDir(cwd);
  await writeFile(issuePath(cwd, issue.id), `${JSON.stringify(issue, null, 2)}\n`, "utf8");
}

async function listIssues(cwd: string): Promise<IssueRecord[]> {
  if (!existsSync(issuesDir(cwd))) return [];

  const entries = await readdir(issuesDir(cwd));
  const issues = await Promise.all(
    entries
      .filter((entry) => entry.endsWith(".json"))
      .map(async (entry) => {
        const raw = await readFile(join(issuesDir(cwd), entry), "utf8");
        return JSON.parse(raw) as IssueRecord;
      }),
  );

  return issues.sort((a, b) => a.id.localeCompare(b.id));
}

async function nextIssueId(cwd: string): Promise<string> {
  const issues = await listIssues(cwd);
  const max = issues.reduce((acc, issue) => {
    const match = issue.id.match(/^ISSUE-(\d+)$/);
    if (!match) return acc;
    return Math.max(acc, Number.parseInt(match[1] ?? "0", 10));
  }, 0);
  return `ISSUE-${String(max + 1).padStart(3, "0")}`;
}

function summarizeIssues(issues: IssueRecord[]) {
  const open = issues.filter((issue) => issue.status === "open");
  const closed = issues.filter((issue) => issue.status === "closed");
  const p1 = open.filter((issue) => issue.priority === "p1").length;
  const p2 = open.filter((issue) => issue.priority === "p2").length;
  const p3 = open.filter((issue) => issue.priority === "p3").length;
  return { open, closed, p1, p2, p3 };
}

function renderIssueSummary(theme: Theme, issues: IssueRecord[]) {
  const summary = summarizeIssues(issues);
  const parts = [
    theme.fg("accent", "Issues"),
    theme.fg("text", `${summary.open.length} open`),
    theme.fg("dim", `${summary.closed.length} closed`),
    theme.fg("error", `P1:${summary.p1}`),
    theme.fg("warning", `P2:${summary.p2}`),
    theme.fg("success", `P3:${summary.p3}`),
  ];
  return parts.join(theme.fg("dim", " • "));
}

class IssuesOverlay implements Focusable {
  focused = false;
  private selected = 0;

  constructor(
    private theme: Theme,
    private issues: IssueRecord[],
    private done: (result?: string) => void,
  ) {}

  handleInput(data: string): void {
    if (matchesKey(data, "escape")) {
      this.done();
      return;
    }
    if (matchesKey(data, "up")) {
      this.selected = Math.max(0, this.selected - 1);
      return;
    }
    if (matchesKey(data, "down")) {
      this.selected = Math.min(Math.max(0, this.issues.length - 1), this.selected + 1);
      return;
    }
    if (matchesKey(data, "return")) {
      const issue = this.issues[this.selected];
      this.done(issue ? issue.id : undefined);
    }
  }

  render(width: number): string[] {
    const w = Math.min(width, 88);
    const inner = w - 2;
    const pad = (s: string) => s + " ".repeat(Math.max(0, inner - visibleWidth(s)));
    const row = (content: string) => this.theme.fg("border", "│") + pad(content) + this.theme.fg("border", "│");

    const lines: string[] = [];
    lines.push(this.theme.fg("border", `╭${"─".repeat(inner)}╮`));
    lines.push(row(` ${this.theme.fg("accent", "Issue Checklist")}`));
    lines.push(row(` ${renderIssueSummary(this.theme, this.issues)}`));
    lines.push(row(""));

    if (this.issues.length === 0) {
      lines.push(row(` ${this.theme.fg("dim", "No issues yet")}`));
    } else {
      for (let i = 0; i < this.issues.length; i++) {
        const issue = this.issues[i]!;
        const selected = i === this.selected;
        const prefix = selected ? this.theme.fg("accent", "▶ ") : "  ";
        const status = issue.status === "open" ? this.theme.fg("success", "[ ]") : this.theme.fg("dim", "[x]");
        const priorityColor = issue.priority === "p1" ? "error" : issue.priority === "p2" ? "warning" : "success";
        const text = `${prefix}${status} ${issue.id} ${this.theme.fg(priorityColor, issue.priority.toUpperCase())} ${issue.title}`;
        lines.push(row(` ${text}`));
      }
    }

    lines.push(row(""));
    lines.push(row(` ${this.theme.fg("dim", "↑↓ navigate • Enter select • Esc close")}`));
    lines.push(this.theme.fg("border", `╰${"─".repeat(inner)}╯`));
    return lines;
  }

  invalidate(): void {}
  dispose(): void {}
}

const issueTrackerTool = defineTool<any>({
  name: "issue_tracker",
  label: "Issue Tracker",
  description: "Manage project-local structured issues stored as JSON files in .pi/issues/.",
  parameters: Type.Object({
    action: Type.String({ description: "One of: list, get, create, update, append_note, close, reopen" }),
    id: Type.Optional(Type.String({ description: "Issue ID, e.g. ISSUE-001" })),
    title: Type.Optional(Type.String({ description: "Issue title" })),
    priority: Type.Optional(Type.String({ description: "Priority: p1, p2, or p3" })),
    tags: Type.Optional(Type.Array(Type.String(), { description: "Issue tags" })),
    text: Type.Optional(Type.String({ description: "Note text for append_note or create" })),
    status: Type.Optional(Type.String({ description: "Status filter: open or closed" })),
    tag: Type.Optional(Type.String({ description: "Filter list results by tag" })),
  }),
  async execute(_toolCallId, params) {
    const cwd = process.cwd();

    if (params.action === "list") {
      const issues = await listIssues(cwd);
      const filtered = issues.filter((issue) => {
        if (params.status && issue.status !== params.status) return false;
        if (params.priority && issue.priority !== params.priority) return false;
        if (params.tag && !issue.tags.includes(params.tag)) return false;
        return true;
      });

      return {
        content: [{ type: "text", text: JSON.stringify(filtered, null, 2) }],
        details: { status: "ok", action: "list", issues: filtered },
      };
    }

    if (params.action === "create") {
      if (!params.title) {
        return {
          content: [{ type: "text", text: "Error: title is required" }],
          details: { status: "error", action: "create", message: "title is required" },
        };
      }

      const timestamp = nowIso();
      const issue: IssueRecord = {
        id: await nextIssueId(cwd),
        title: params.title,
        status: "open",
        priority: (params.priority as IssuePriority | undefined) ?? "p2",
        tags: params.tags ?? [],
        created_at: timestamp,
        updated_at: timestamp,
        notes: params.text ? [{ created_at: timestamp, text: params.text }] : [],
      };

      await writeIssue(cwd, issue);
      return {
        content: [{ type: "text", text: JSON.stringify(issue, null, 2) }],
        details: { status: "ok", action: "create", issue },
      };
    }

    if (!params.id) {
      return {
        content: [{ type: "text", text: "Error: id is required" }],
        details: { status: "error", action: params.action, message: "id is required" },
      };
    }

    const issue = await readIssue(cwd, params.id);
    if (!issue) {
      return {
        content: [{ type: "text", text: `Error: issue ${params.id} not found` }],
        details: { status: "error", action: params.action, message: "not found", id: params.id },
      };
    }

    if (params.action === "get") {
      return {
        content: [{ type: "text", text: JSON.stringify(issue, null, 2) }],
        details: { status: "ok", action: "get", issue },
      };
    }

    if (params.action === "update") {
      issue.title = params.title ?? issue.title;
      issue.priority = (params.priority as IssuePriority | undefined) ?? issue.priority;
      issue.tags = params.tags ?? issue.tags;
      issue.updated_at = nowIso();
      await writeIssue(cwd, issue);
      return {
        content: [{ type: "text", text: JSON.stringify(issue, null, 2) }],
        details: { status: "ok", action: "update", issue },
      };
    }

    if (params.action === "append_note") {
      if (!params.text) {
        return {
          content: [{ type: "text", text: "Error: text is required" }],
          details: { status: "error", action: "append_note", message: "text is required" },
        };
      }
      issue.notes.push({ created_at: nowIso(), text: params.text });
      issue.updated_at = nowIso();
      await writeIssue(cwd, issue);
      return {
        content: [{ type: "text", text: JSON.stringify(issue, null, 2) }],
        details: { status: "ok", action: "append_note", issue },
      };
    }

    if (params.action === "close") {
      issue.status = "closed";
      issue.updated_at = nowIso();
      await writeIssue(cwd, issue);
      return {
        content: [{ type: "text", text: JSON.stringify(issue, null, 2) }],
        details: { status: "ok", action: "close", issue },
      };
    }

    if (params.action === "reopen") {
      issue.status = "open";
      issue.updated_at = nowIso();
      await writeIssue(cwd, issue);
      return {
        content: [{ type: "text", text: JSON.stringify(issue, null, 2) }],
        details: { status: "ok", action: "reopen", issue },
      };
    }

    return {
      content: [{ type: "text", text: `Error: unsupported action ${params.action}` }],
      details: { status: "error", action: params.action, message: "unsupported action" },
    };
  },
});

export default function (pi: ExtensionAPI) {
  pi.registerTool(issueTrackerTool);

  async function refreshIssueUI(ctx: { cwd: string; hasUI: boolean; ui: any }) {
    const issues = await listIssues(ctx.cwd);
    if (!ctx.hasUI) return;
    const theme = ctx.ui.theme;
    ctx.ui.setStatus("issue-summary", renderIssueSummary(theme, issues));

    const openIssues = issues.filter((issue) => issue.status === "open");
    const widgetLines = openIssues.length === 0
      ? [theme.fg("dim", "No open issues")]
      : openIssues.slice(0, 6).map((issue) => {
          const priorityColor = issue.priority === "p1" ? "error" : issue.priority === "p2" ? "warning" : "success";
          return `${theme.fg(priorityColor, "•")} ${issue.id} ${issue.title}`;
        });
    ctx.ui.setWidget("issue-checklist", widgetLines);
  }

  pi.on("session_start", async (_event, ctx) => {
    await refreshIssueUI(ctx);
  });

  pi.on("tool_result", async (event, ctx) => {
    if (event.toolName === "issue_tracker") {
      await refreshIssueUI(ctx);
    }
  });

  pi.registerCommand("issues", {
    description: "Show interactive issue checklist overlay",
    handler: async (_args: string, ctx: ExtensionCommandContext) => {
      const issues = await listIssues(ctx.cwd);
      const selected = await ctx.ui.custom<string | undefined>(
        (_tui, theme, _kb, done) => new IssuesOverlay(theme, issues, done),
        { overlay: true },
      );
      if (selected) {
        ctx.ui.notify(`Selected ${selected}`, "info");
      }
    },
  });
}
