import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

const ALIASES = {
  "re:feature": "feature",
  "re:existing_repo": "existing_repo",
  "re:new_repo": "new_repo",
} as const;

type AliasName = keyof typeof ALIASES;

export default function (pi: ExtensionAPI) {
  for (const [alias, target] of Object.entries(ALIASES) as [AliasName, string][]) {
    pi.registerCommand(alias, {
      description: `Compat alias: /${alias} → /${target}`,
      handler: (args) => {
        const trimmed = args.trim();
        const message = trimmed ? `/${target} ${trimmed}` : `/${target}`;
        pi.sendUserMessage(message);
      },
    });
  }
}
