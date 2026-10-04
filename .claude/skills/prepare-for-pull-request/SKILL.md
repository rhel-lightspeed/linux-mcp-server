---
name: prepare-for-pull-request
description: Run make verify, then summarize changes since a given commit SHA into a PR description
disable-model-invocation: true
allowed-tools: Bash(make *) Bash(git diff *) Bash(git log *) Bash(git status) Bash(git rev-parse *) Bash(git reflog *)
argument-hint: "[base-commit-sha]"
---

Prepare a pull request description by verifying the code and summarizing all changes since a base commit.

## Step 0: Determine the base ref

If `$ARGUMENTS` is provided (e.g. a SHA, `main`, `HEAD~3`), use it as the base ref.

If `$ARGUMENTS` is empty, auto-detect the branch point:

1. Get the current branch name: `git rev-parse --abbrev-ref HEAD`
2. Find where this branch was created from using reflog: `git reflog show <current-branch> --format='%H %gs'`
3. Look for the entry with `branch: Created from` in the reflog output — the SHA on that line is where the branch was born.
4. Use that SHA as the base ref. Tell the user which base ref was auto-detected so they can confirm.

If the reflog doesn't contain a `Created from` entry (e.g. the reflog was pruned), fall back to asking the user for the base ref.

## Step 1: Run verification

Run `make verify` to sync dependencies and execute all CI checks (lint, format, types, tests).

- If it passes, proceed to step 2.
- If it fails, stop and show the user the errors. Offer to help fix them before continuing. Do NOT proceed to PR description generation until verification passes.

## Step 2: Gather change information

Run these commands to understand the full scope of changes:

- `git log --oneline $ARGUMENTS..HEAD` — list all commits being included.
- `git log --format="### %s%n%n%b" $ARGUMENTS..HEAD` — get full commit messages with bodies.
- `git diff --stat $ARGUMENTS..HEAD` — file-level summary of what changed.
- `git diff $ARGUMENTS..HEAD` — full diff for detailed analysis.

**Uncommitted changes:** By default, only include committed changes in the PR description. Ignore uncommitted (staged or unstaged) files unless the user explicitly mentions or asks to include them.

## Step 3: Analyze and categorize

Review all commits and the diff to understand:

- **The problem or gap that motivated this work** — what was missing, broken, or insufficient before this PR? Derive this from commit messages, code comments, and the nature of the changes themselves.
- What features were added, bugs fixed, or refactors made.
- Which project components were affected — map changes to the project architecture:
  - **Tools** (`tools/*.py`) — which MCP tools were added or modified?
  - **Parsers/Formatters** (`parsers.py`, `formatters.py`) — output parsing or display changes?
  - **Connection** (`connection/ssh.py`) — SSH or remote execution changes?
  - **Models** (`models.py`) — data model changes?
  - **Config** (`config.py`) — new env vars or configuration options?
  - **Gatekeeper** (`gatekeeper/`) — script validation changes?
  - **MCP App** (`mcp-app/`) — UI changes?
  - **Tests** (`tests/`) — new or modified test coverage?
  - **CI/Docs/Scripts** — infrastructure changes?
- Any breaking changes, new dependencies, or new `LINUX_MCP_*` configuration variables.

## Step 4: Generate the PR description

Produce a PR description in this format:

```markdown
## Motivation
<!-- 1-3 sentences explaining the problem, gap, or motivation that drove this PR. Answer: what was the situation before, and why was it insufficient? Do NOT describe what the code does here — focus on the reason the work was needed. -->

## Summary
<!-- 1-3 bullet points describing the high-level approach taken to address the problem above -->

## Changes
<!-- Bulleted list of specific changes, grouped by affected project area (e.g. Tools, Parsers, Models, Config, Tests, CI, Docs). Use the project's component names, not generic categories. -->

## Test plan
<!-- How the changes were verified — reference make verify passing, plus any manual testing or specific test cases added -->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Rules:
- **"Motivation" comes first** and must answer "what problem does this solve?" — not "what does this PR do?"
- Keep the summary concise — focus on the approach, not a line-by-line rehash.
- In the Changes section, group by project component (Tools, Connection, Models, Config, Tests, etc.) rather than generic categories.
- Call out breaking changes, migration steps, or new `LINUX_MCP_*` env vars prominently.
- Mention new dependencies or changes to `pyproject.toml` if applicable.

## Step 5: Present the result

Show the generated PR description in a code block. Ask the user if they'd like to:
1. Create the PR now using `gh pr create` with this description
2. Edit the description first
3. Regenerate with different emphasis
