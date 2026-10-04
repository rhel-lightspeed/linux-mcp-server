---
name: generate-commit-message
description: Use git diff to analyze changes and generate a conventional commit message following this project's conventions from AGENTS.md
disable-model-invocation: true
allowed-tools: Bash(git diff *) Bash(git status) Bash(git log *)
---

Generate a commit message for the current changes by following these steps:

## 1. Parse arguments

`$ARGUMENTS` may contain additional context for the commit message.

## 2. Gather context

- Run `git status` to see what files are staged vs unstaged.
- Run `git diff --cached` to see staged changes. If nothing is staged, inform the user that nothing is staged and stop — do not fall back to unstaged changes.
- Run `git log --oneline -10` to see recent commit messages for style reference.

## 3. Analyze the changes

Identify the **type** based on the nature of the change. This project uses both standard Conventional Commit types and module-level types:

**Standard types:** `feat`, `fix`, `refactor`, `test`, `docs`, `ci`, `chore`, `perf`, `style`, `build`

**Module-level types** — used when the change is entirely within one of these subsystems:
- `run_script` — changes scoped to `tools/run_script.py` or the run_script workflow
- `eval` — changes to the gatekeeper evaluation/benchmark system

Identify the **scope** from the area of the codebase affected. Use these established scopes:

| Scope | When to use |
|-------|------------|
| `ssh` | `connection/ssh.py` or SSH-related logic |
| `run_script` | `tools/run_script.py` (use as scope with `fix`/`feat`, or as standalone type) |
| `deps` | dependency version bumps (`chore(deps)`) |
| `ci` | CI/CD workflows in `.github/` |
| `scripts` | utility scripts in `scripts/` |
| `functional` | functional/integration tests in `tests/functional/` |
| `storage` | `tools/storage.py` or storage-related tools |
| `models` | `models.py` data model changes |
| `validation` | `utils/validation.py` input validation |
| `mcp-apps(ui)` | React UI in `mcp-app/` (nested scope) |

**Scope rules:**
- Omit scope when the change spans multiple areas or no established scope fits.
- When using a module-level type like `run_script:` or `eval:`, do not add a redundant scope.
- For dependency updates, always use `chore(deps):`.

## 4. Generate the commit message

Follow the [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): short imperative description
```

Or for module-level types:

```
type: short imperative description
```

**Subject line rules:**
- Imperative mood, lowercase start, no period at the end.
- Under 72 characters total.
- Focus on **why** or **what changed**, not how.
- If there is a `$ARGUMENTS` value, use it as additional context for the message.

**Body** (optional — only when the subject line alone doesn't capture the reasoning):
```

Motivation and context behind the change.
Wrap at 72 characters per line.
```

## 5. Present the result

Show the generated commit message in a code block so the user can review it. Ask the user if they'd like to:
1. Use the message as-is (run `git commit` with it)
2. Edit it before committing
3. Regenerate with different emphasis
