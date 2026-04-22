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
  description:
    "Ask the user a structured question with optional choices, freeform input, and optional notes. Use this tool whenever the LLM needs user input to proceed.",
  promptSnippet: "Ask the user a question and wait for their answer.",
  promptGuidelines: [
    "Use ask_user_question whenever you need clarification, confirmation, or a choice from the user before proceeding.",
  ],
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
    allow_notes: Type.Optional(
      Type.Boolean({ description: "Allow the user to attach additional notes to their answer" }),
    ),
    notes_placeholder: Type.Optional(
      Type.String({ description: "Placeholder text for optional notes" }),
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
    const allowNotes = params.allow_notes ?? false;
    const notesPlaceholder = params.notes_placeholder ?? "Add optional notes...";

    let answerType: "option" | "freeform" | undefined;
    let answerValue = "";
    let answerLabel = "";

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
        answerType = "option";
        answerValue = selectedOption.value;
        answerLabel = selectedOption.label;
      }
    }

    if (!answerType) {
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
          answerType = "freeform";
          answerValue = trimmed;
          answerLabel = trimmed;
          break;
        }

        ctx.ui.notify("Answer required", "warning");
      }
    }

    let notes: string | undefined;
    if (allowNotes) {
      const addNotes = await ctx.ui.confirm("Add notes?", "Would you like to attach extra notes to this answer?");
      if (addNotes) {
        const noteValue = await ctx.ui.editor("Answer notes", notesPlaceholder);
        if (noteValue !== undefined) {
          const trimmedNotes = noteValue.trim();
          if (trimmedNotes.length > 0) {
            notes = trimmedNotes;
          }
        }
      }
    }

    const text = notes
      ? `User answered: ${answerLabel}\nNotes: ${notes}`
      : `User answered: ${answerLabel}`;

    return {
      content: [{ type: "text", text }],
      details: {
        status: "answered",
        question: params.question,
        answer: {
          type: answerType,
          value: answerValue,
          label: answerLabel,
        },
        notes,
      },
    };
  },
});

export default function (pi: ExtensionAPI) {
  pi.registerTool(askUserQuestionTool);
}
