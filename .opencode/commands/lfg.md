---
description: Full autonomous engineering workflow
argument-hint: "[feature description] [--strategy=<name>]"
disable-model-invocation: true
---

**Default strategy:** `full-process`. If a `--strategy=<name>` argument is provided, load `references/strategies/<name>.md` and apply its phase overrides. Skip phases where the strategy sets `enabled: false`.

Run these slash commands in order. Do not do anything else.

1. `/ralph-wiggum:ralph-loop "finish all slash commands" --completion-promise "DONE"`
2. `/workflows:plan $ARGUMENTS`
3. `/compound-engineering:deepen-plan`
4. `/workflows:work`
5. `/workflows:review`
6. `/compound-engineering:resolve_todo_parallel`
7. `/compound-engineering:test-browser`
8. `/compound-engineering:feature-video`
9. Output `<promise>DONE</promise>` when video is in PR

Start with step 1 now.
