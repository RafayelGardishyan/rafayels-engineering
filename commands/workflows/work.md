---
name: workflows:work
description: Execute work plans efficiently while maintaining quality and finishing features
argument-hint: "[plan file, specification, or todo file path]"
---

# Work Plan Execution Command

Execute a work plan efficiently while maintaining quality and finishing features.

## Introduction

This command takes a work document (plan, specification, or todo file) and executes it systematically. The focus is on **shipping complete features** by understanding requirements quickly, following existing patterns, and maintaining quality throughout.

## Input Document

<input_document> #$ARGUMENTS </input_document>

## Execution Workflow

### Phase 0.5: Retrieve Relevant Cases from Memory

Before starting work, query memory for relevant past implementation cases:

```bash
${CLAUDE_PLUGIN_ROOT}/skills/memory/scripts/memory query \
  "<plan title or feature description>" --phase work --k 3 --format md 2>/dev/null
```

If cases are returned, include them in the work context. Pay attention to past failure cases — they list things to avoid. Exit code 75 or empty output means proceed without injection.

### Phase 0.6: Build the todo list from plan + tracked issues

Before implementation starts:

- Read the plan file completely.
- Create a concrete todo list from the implementation phases/checklists.
- Query `issue_tracker list` for relevant open issues (especially tags like `plan`, `work`, `review`, `open-question`, or feature-specific tags).
- Merge plan tasks and tracked issues into one execution list.
- **Work must proceed through this todo list in order or dependency order.**
- **When a task or tracked issue is completed, mark it complete immediately.**

Tracked issue behavior:
- If a todo corresponds to a tracked issue, close it via `issue_tracker close` when complete.
- If a task reveals new work that should persist beyond the current turn, create a new issue via `issue_tracker create`.
- If partial progress matters, append progress notes via `issue_tracker append_note`.

### Phase 1: Quick Start

1. **Read Plan and Clarify**

   - Read the work document completely
   - Review any references or links provided in the plan
   - If anything is unclear or ambiguous, ask clarifying questions now
   - Get user approval to proceed
   - **Do not skip this** - better to ask questions now than build the wrong thing

2. **Setup Environment**

   First, check the current branch:

   ```bash
   current_branch=$(git branch --show-current)
   default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')

   # Fallback if remote HEAD isn't set
   if [ -z "$default_branch" ]; then
     default_branch=$(git rev-parse --verify origin/main >/dev/null 2>&1 && echo "main" || echo "master")
   fi
   ```

   **If already on a feature branch** (not the default branch):
   - Ask: "Continue working on `[current_branch]`, or create a new branch?"
   - If continuing, proceed to step 3
   - If creating new, follow Option A or B below

   **If on the default branch**, choose how to proceed:

   **Option A: Create a new branch**
   ```bash
   git pull origin [default_branch]
   git checkout -b feature-branch-name
   ```
   Use a meaningful name based on the work (e.g., `feat/user-authentication`, `fix/email-validation`).

   **Option B: Use a worktree (recommended for parallel development)**
   ```bash
   skill: git-worktree
   # The skill will create a new branch from the default branch in an isolated worktree
   ```

   **Option C: Continue on the default branch**
   - Requires explicit user confirmation
   - Only proceed after user explicitly says "yes, commit to [default_branch]"
   - Never commit directly to the default branch without explicit permission

3. **Create Todo List**
   - Build the active todo list from the plan and `issue_tracker`
   - Include dependencies between tasks
   - Prioritize based on what needs to be done first
   - Include testing and quality check tasks
   - Keep tasks specific and completable
   - **Every finished task must be marked complete in the list and in `issue_tracker` if applicable**

### Phase 2: Execute

1. **Task Execution Loop**

   For each task in priority order:

   ```
   while (tasks remain):
     - Mark task as in_progress in the active todo list
     - Read any referenced files from the plan
     - Look for similar patterns in codebase
     - FOR pure coding tasks: delegate to Codex via the codex-bridge MCP server first
     - Review Codex output; integrate, fix, or iterate as needed
     - Implement any remaining work following existing conventions
     - Write tests for new functionality
     - Run tests after changes
     - Mark task as completed in the active todo list
     - If linked to an issue_tracker item: close it or append completion notes immediately
     - Mark off the corresponding checkbox in the plan file ([ ] → [x])
     - Evaluate for incremental commit (see below)
   ```

   **IMPORTANT**:
   - Always update the original plan document by checking off completed items.
   - Use the `Edit` tool to change `- [ ]` to `- [x]` for each task you finish.
   - If using tracked issues, keep them synchronized with the implementation state.
   - Do not leave completed work open in the issue list.

2. **Incremental Commits**

   After completing each task, evaluate whether to create an incremental commit:

   | Commit when... | Don't commit when... |
   |----------------|---------------------|
   | Logical unit complete (model, service, component) | Small part of a larger unit |
   | Tests pass + meaningful progress | Tests failing |
   | About to switch contexts (backend → frontend) | Purely scaffolding with no behavior |
   | About to attempt risky/uncertain changes | Would need a "WIP" commit message |

   **Heuristic:** "Can I write a commit message that describes a complete, valuable change? If yes, commit. If the message would be 'WIP' or 'partial X', wait."

3. **Delegate to Codex**

   When a task is a pure coding task (implement X, refactor Y, add Z) with clear requirements:

   1. **Call `delegate_coding_task`** from the `codex-bridge` MCP server
   2. **Provide context**: include `task_description`, `file_paths`, and any relevant `context`
   3. **Review the response**: check `status`, `final_message`, and `file_changes`
   4. **Integrate or iterate**: if Codex's output is good, commit it; if incomplete, call again with a follow-up prompt
   5. **Fall back to manual implementation** only when:
      - The task requires deep project-specific convention knowledge
      - Codex fails repeatedly or produces incorrect output
      - The user explicitly requested manual implementation

4. **Follow Existing Patterns**

   - The plan should reference similar code - read those files first
   - Match naming conventions exactly
   - Reuse existing components where possible
   - Follow project coding standards (see CLAUDE.md)
   - When in doubt, grep for similar implementations

5. **Test Continuously**

   - Run relevant tests after each significant change
   - Don't wait until the end to test
   - Fix failures immediately
   - Add new tests for new functionality

6. **Track Progress**
   - Keep the active todo list updated as you complete tasks
   - Keep `issue_tracker` synchronized with actual work progress
   - Note any blockers or unexpected discoveries
   - Create new tracked issues if scope expands in a way that should persist
   - Keep user informed of major milestones

### Phase 3: Quality Check

1. **Run Core Quality Checks**

   Always run before submitting:

   ```bash
   # Run full test suite (use project's test command)
   # Run linting (per CLAUDE.md)
   ```

2. **Final Validation**
   - All work todos marked completed
   - All linked issues updated or closed
   - All tests pass
   - Linting passes
   - Code follows existing patterns
   - No console errors or warnings

### Phase 4: Ship It

1. **Create Commit**

   ```bash
   git add .
   git status
   git diff --staged
   git commit -m "feat(scope): description of what and why"
   ```

2. **Create Pull Request**

   ```bash
   git push -u origin feature-branch-name
   gh pr create ...
   ```

3. **Notify User**
   - Summarize what was completed
   - Link to PR
   - Note any follow-up work needed
   - Suggest next steps if applicable

4. **Capture Case to Memory**

   After the PR is created, capture this work as a memory case.

5. **Emit Signals**

   Emit CI / review / merge signals as appropriate.

## Key Principles

- Work from a **real todo list**, not vague narrative progress
- Keep **plan checkboxes** and **tracked issues** synchronized with actual execution
- When work is done, **mark it done immediately**
- Ship complete features, not half-finished hidden progress

## Quality Checklist

Before creating PR, verify:

- [ ] All clarifying questions asked and answered
- [ ] All work todos marked completed
- [ ] All relevant `issue_tracker` items updated or closed
- [ ] Tests pass
- [ ] Linting passes
- [ ] Code follows existing patterns
- [ ] Commit messages follow conventional format

## Common Pitfalls to Avoid

- **Analysis paralysis**
- **Skipping clarifying questions**
- **Ignoring plan references**
- **Testing only at the end**
- **Leaving completed issues open**
- **Updating the plan but not the tracked issues**
- **Updating tracked issues but not the plan**
