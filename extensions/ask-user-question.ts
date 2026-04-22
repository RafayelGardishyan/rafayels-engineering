import { Type } from "@mariozechner/pi-ai";
import { defineTool, type ExtensionAPI } from "@mariozechner/pi-coding-agent";

type QuestionOption = {
  value: string;
  label: string;
  description?: string;
};

const QuestionOptionSchema = Type.Object({
  value: Type.String({ description: "The value returned when selected" }),
  label: Type.String({ description: "Display label for the option" }),
  description: Type.Optional(Type.String({ description: "Optional description shown below the option" })),
});

const askUserQuestionTool = defineTool({
  name: "ask_user_question",
  label: "Ask User Question",
  description: "Ask the user a structured question with optional choices and freeform input.",
  parameters: Type.Object({
    question: Type.String({ description: "The question to ask the user" }),
    options: Type.Optional(
      Type.Array(QuestionOptionSchema, { description: "Optional list of selectable answers" }),
    ),
    allow_freeform: Type.Optional(
      Type.Boolean({ description: "Allow the user to enter a custom freeform answer" }),
    ),
    placeholder: Type.Optional(
      Type.String({ description: "Placeholder text for freeform input" }),
    ),
    required: Type.Optional(
      Type.Boolean({ description: "Whether an answer is required for freeform input" }),
    ),
  }),
  async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
    if (!ctx.hasUI) {
      return {
        content: [{ type: "text", text: "Error: UI not available" }],
        details: { status: "cancelled", reason: "ui_unavailable", question: params.question },
      };
    }

    const options = params.options ?? [];
    const allowFreeform = params.allow_freeform ?? false;
    const required = params.required ?? false;
    const placeholder = params.placeholder ?? "Type your answer...";

    if (options.length > 0) {
      const labels = options.map((option: QuestionOption) =>
        option.description ? `${option.label} — ${option.description}` : option.label,
      );
      if (allowFreeform) {
        labels.push("Other...");
      }

      const selected = await ctx.ui.select(params.question, labels);
      if (!selected) {
        return {
          content: [{ type: "text", text: "User cancelled the question" }],
          details: { status: "cancelled", question: params.question },
        };
      }

      const freeformSelected = allowFreeform && selected === "Other...";
      if (!freeformSelected) {
        const selectedIndex = labels.indexOf(selected);
        const selectedOption = options[selectedIndex];
        return {
          content: [{ type: "text", text: `User selected: ${selectedOption.label}` }],
          details: {
            status: "answered",
            question: params.question,
            answer: {
              type: "option",
              value: selectedOption.value,
              label: selectedOption.label,
            },
          },
        };
      }
    }

    while (true) {
      const answer = await ctx.ui.input(params.question, placeholder);
      if (answer === undefined) {
        return {
          content: [{ type: "text", text: "User cancelled the question" }],
          details: { status: "cancelled", question: params.question },
        };
      }

      const trimmed = answer.trim();
      if (!required || trimmed.length > 0) {
        return {
          content: [{ type: "text", text: `User answered: ${trimmed}` }],
          details: {
            status: "answered",
            question: params.question,
            answer: {
              type: "freeform",
              value: trimmed,
              label: trimmed,
            },
          },
        };
      }

      ctx.ui.notify("Answer required", "warning");
    }
  },
});

export default function (pi: ExtensionAPI) {
  pi.registerTool(askUserQuestionTool);
}
