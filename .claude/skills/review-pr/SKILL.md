---
name: review-pr
description: Review a pull request by URL for code format, types, semantic correctness, readability, redundant logic, bugs, and security concerns
disable-model-invocation: true
allowed-tools: Bash(gh pr *) Bash(gh api *) Bash(git diff *) Bash(git log *) Bash(git status) Bash(git fetch *) Bash(git checkout *) Bash(git rev-parse *) Bash(git merge-base *) Bash(make lint) Bash(make format) Bash(make types) Bash(make test) Read
argument-hint: "<pr-url>"
---

Review a pull request for code quality issues across six dimensions: format, types, semantic correctness, readability, redundant logic, and bugs/security.

## Step 0: Fetch PR information

`$ARGUMENTS` must be a GitHub PR URL (e.g. `https://github.com/owner/repo/pull/123`).

If `$ARGUMENTS` is empty, ask the user for the PR URL. Do not proceed without it.

1. Extract the PR number from the URL.
2. Run `gh pr view <pr-url> --json number,title,baseRefName,headRefName,commits,files` to get PR metadata.
3. Fetch the PR branch locally:
   - `git fetch origin pull/<number>/head:pr-<number>` to create a local ref for the PR.
   - Determine the merge base: `git merge-base origin/<baseRefName> pr-<number>`
4. Use the merge base as the base ref for all diff commands.

Tell the user which PR you're reviewing (number, title, head branch, base branch).

## Step 1: Gather changes

Run these commands to understand the full scope of changes:

- `git log --oneline <merge-base>..pr-<number>` — list all commits in the PR.
- `git diff --stat <merge-base>..pr-<number>` — file-level summary of what changed.
- `git diff <merge-base>..pr-<number>` — full diff for detailed analysis.

Read every changed file in full (from the PR branch) so you can evaluate changes in their surrounding context, not just the diff hunks in isolation. Use `git show pr-<number>:<file-path>` to read files from the PR branch without switching branches.

## Step 2: Format check

Run `make lint` and `make format` against the PR branch to check for formatting and linting violations.

To do this without modifying the current working tree:
- Check out the PR branch: `git checkout pr-<number>`
- Run `make lint` and `make format`.
- After the review is complete (Step 8), check out the original branch.

Report results:
- **Pass** — no issues found.
- **Fail** — list every violation with file path, line number, and the rule ID. Group by file.

Do NOT auto-fix. Only report.

## Step 3: Type check

Run `make types` to run pyright on the PR branch.

Report results:
- **Pass** — no type errors.
- **Fail** — list every error with file path, line number, and the pyright message. Group by file.

For the `mcp-app/` TypeScript code, if any `.ts` or `.tsx` files are in the diff, note that TypeScript type checking should be run separately inside `mcp-app/` if a tsconfig and type-check script exist there.

## Step 4: Semantic review

Analyze every changed file for semantic correctness. For each file, check:

1. **Behavioral changes** — Does the change alter existing behavior? Is that intentional or an accidental regression? Look for:
   - Changed return values, error handling, or control flow.
   - Modified default values or function signatures.
   - Altered query/filter logic.

2. **Edge cases** — Are there inputs or states the new code doesn't handle?
   - Empty/null/zero-length inputs.
   - Boundary values (off-by-one, max int, empty string vs None).
   - Concurrent or async race conditions.

3. **API contract consistency** — Do changes to models, tool signatures, or config stay consistent across:
   - `models.py` ↔ `parsers.py` ↔ `formatters.py`
   - `commands.py` ↔ `tools/*.py`
   - `config.py` env var names ↔ documentation

4. **Test coverage** — Are new code paths covered by tests? Flag any added logic that lacks a corresponding test case.

Report each finding with:
- File path and line number(s).
- What the issue is.
- Severity: **critical** (likely bug/regression), **warning** (potential issue), or **info** (suggestion).

## Step 5: Readability and redundancy review

Evaluate the changed code for maintainability:

1. **Readability issues:**
   - Overly complex expressions that should be broken up.
   - Unclear variable or function names.
   - Deeply nested logic (3+ levels) that could be flattened with early returns or guard clauses.
   - Magic numbers or strings that should be named constants.
   - Functions doing too many things (violating single responsibility).

2. **Redundant logic:**
   - Duplicate code across the diff or between the diff and existing code.
   - Conditions that are always true/false.
   - Unnecessary intermediate variables or re-assignments.
   - Dead code (unreachable branches, unused imports, unused variables).
   - Over-engineered abstractions for simple operations.

Report each finding with file path, line number(s), what the issue is, and a concrete suggestion for improvement.

## Step 6: Bug and security review

Scan changes for bugs and security concerns, with special attention to this project's security model (read-only tools, SSH key auth, input validation):

1. **Bugs:**
   - Incorrect exception handling (swallowing errors, catching too broadly).
   - Resource leaks (unclosed connections, file handles).
   - Async issues (missing `await`, unawaited coroutines).
   - Incorrect use of mutable default arguments.

2. **Security (OWASP + project-specific):**
   - **Command injection** — Any user input reaching shell commands without validation. Check against the project's `commands.py` allowlist pattern.
   - **Path traversal** — File path parameters that aren't validated against allowlists (see `ALLOWED_LOG_PATHS`, `MAX_FILE_READ_BYTES`).
   - **Information disclosure** — Sensitive data in logs, error messages, or tool outputs. Check that `audit.py` redaction covers new fields.
   - **SSH security** — Any weakening of host key verification, key-based auth, or connection pooling.
   - **Read-only violation** — Any tool missing `readOnlyHint=True` or performing writes without going through the gatekeeper.
   - **Input validation** — Missing or insufficient validation on tool parameters (see `utils/validation.py`).
   - **Dependency risks** — New dependencies that are unmaintained, have known CVEs, or pull in excessive transitive deps.

Rate each finding:
- **critical** — Exploitable vulnerability or guaranteed bug. Must fix before merge.
- **warning** — Potential issue depending on context. Should fix or explicitly justify.
- **info** — Defense-in-depth suggestion or minor hardening opportunity.

## Step 7: Run tests

Run `make test` on the PR branch to verify all tests pass.

Report results:
- **Pass** — all tests green, with coverage summary if printed.
- **Fail** — list failing tests with their error messages. Note whether failures are related to the PR changes or pre-existing.

## Step 8: Restore original branch and present summary

Check out the original branch that was active before the review began.

Present the full review in this format:

```
## PR Review: #<number> — <title>
**Branch:** <head> → <base>

### Format & Lint
<results from Step 2>

### Type Check
<results from Step 3>

### Tests
<results from Step 7>

### Semantic Issues
<findings from Step 4, ordered by severity>

### Readability & Redundancy
<findings from Step 5>

### Bugs & Security
<findings from Step 6, ordered by severity>

### Verdict

**<APPROVE | REQUEST CHANGES | NEEDS DISCUSSION>**

<1-3 sentence summary of the overall state of the PR. Call out the most important finding if any.>
```

Verdict criteria:
- **APPROVE** — No critical or warning findings. All checks pass.
- **REQUEST CHANGES** — Any critical finding, or 3+ warnings.
- **NEEDS DISCUSSION** — Warnings that involve design decisions or tradeoffs the author should weigh in on.

After presenting the review, ask the user if they'd like to:
1. Fix the reported issues (offer to help with specific fixes).
2. Re-run the review after making changes.
3. Discuss any specific finding in more detail.
