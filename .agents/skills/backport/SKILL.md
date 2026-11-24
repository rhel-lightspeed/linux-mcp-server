---
name: backport
description: Backport a merged PR from main to a stable release-* branch as a single cherry-picked commit, push it, and file the backport PR. Use when asked to backport a PR number to a stable branch.
argument-hint: <PR number> [release-X.Y.x]
---

# Backport a PR to a stable branch

Stable branches (`release-X.Y.x`) only take bug fixes that have already landed on `main` - see
`docs/development/releasing.md`. PRs land on `main` squashed, so each backport is one cherry-pick.

## Inputs

- **PR number** (required), e.g. `703`.
- **Target branch** (optional). If omitted, use the newest `release-*` branch on origin:
  `git ls-remote --heads origin 'refs/heads/release-*' | sed 's|.*refs/heads/||' | sort -V | tail -1`

## Steps

1. `git fetch origin`, then find the PR's squash commit on main:
   `gh pr view <PR> --json state,mergeCommit,title`. Stop if the PR is not merged.
   Confirm the commit is on `origin/main`.

2. Create the branch from the target:
   `git switch -c backport-<PR>-<branch> origin/<branch>`

3. Cherry-pick **without** `-x` (the trailer is custom): `git cherry-pick <sha>`.
   This keeps the original author.

4. If there are conflicts, resolve them yourself - understand what the original change does and
   adapt it to the stable branch. Stop and ask only if you need input to know how to proceed (e.g. the
   fix depends on a feature that isn't on the branch). Keep notes on everything you had to change.

5. Rewrite the commit message (`git commit --amend`):
   - **Subject:** the original subject with the trailing ` (#<PR>)` removed.
   - **Body:** the original body unchanged, then as the last line:
     `(cherry picked from commit <full sha> - #<PR>)`
   - If the backport needed real changes (conflict resolution beyond trivial context, adaptations),
     add an `Assisted-by: <agent>` trailer - unless the original message
     already has an equivalent `Assisted-by:` / `Co-authored-by:` line for the same agent. No trailer for a
     clean cherry-pick.

6. Run `make verify` (which includes `make test`). Fix failures caused by the backport; if a failure
   is pre-existing on the stable branch or needs a judgment call, stop and report.

7. Push: `git push -u origin backport-<PR>-<branch>`

8. **If the backport was not a straight cherry-pick, stop here.** Summarize what was changed and wait
   for the user's approval before filing the PR.

9. File the PR against the target branch:
   - **Title:** `Backport #<PR> - <original subject without (#PR)> - <branch>`
   - **Body:** `Backport #<PR> to the <branch> branch.`
     If anything non-routine was needed, instead describe what was done and why, and end with
     `🤖 Generated with <agent>` (or your standard trailer for a PR). Nothing else for a clean pick.
   - `gh pr create --base <branch> --head backport-<PR>-<branch> --title ... --body ...`
   - No labels, reviewers, or comments on the original PR.

10. Report the PR URL.
