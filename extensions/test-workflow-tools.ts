import type { ExtensionAPI, ExtensionCommandContext } from "@mariozechner/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.registerCommand("test-ask-user-question", {
    description: "Open a real ask_user_question widget in the current Pi session",
    handler: async (_args: string, ctx: ExtensionCommandContext) => {
      if (!ctx.hasUI) {
        ctx.ui.notify("UI not available", "error");
        return;
      }

      const selected = await ctx.ui.select("Which visual test answer do you want?", [
        "Red",
        "Blue",
        "Green",
        "Other...",
      ]);

      if (!selected) {
        ctx.ui.notify("Question cancelled", "warning");
        return;
      }

      let answer = selected;
      if (selected === "Other...") {
        const custom = await ctx.ui.input("Type your custom answer", "Your answer...");
        if (!custom) {
          ctx.ui.notify("Custom answer cancelled", "warning");
          return;
        }
        answer = custom;
      }

      let noteText = "";
      const addNotes = await ctx.ui.confirm("Add notes?", "Would you like to attach notes to your answer?");
      if (addNotes) {
        const notes = await ctx.ui.editor("Answer notes", "Add optional notes...");
        if (notes) {
          noteText = notes.trim();
        }
      }

      if (noteText) {
        ctx.ui.notify(`Selected: ${answer} (+ notes)`, "info");
      } else {
        ctx.ui.notify(`Selected: ${answer}`, "info");
      }
    },
  });
}
