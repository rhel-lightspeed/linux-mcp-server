---
name: relnotes
description: Write the curated release notes for a published linux-mcp-server release and update its GitHub release. Use after a release tag has been pushed and the GitHub release exists, e.g. "/relnotes 1.9.0".
argument-hint: <version, e.g. 1.9.0>
---

# Release notes

The release workflow publishes a GitHub release with GitHub's auto-generated notes: one line per
merged PR, Renovate and CI churn included. This skill replaces them with short, curated notes
written for **users** of linux-mcp-server. Write them from scratch; do not edit the generated list
line by line.

The argument is the release tag (for example `1.9.0`). If none is given, use the most recent
release from `gh release list`.

## 1. Find the range

- The tag must have a GitHub release (`gh release view <tag>`). `.post<N>` tags never have one
  (see `docs/development/releasing.md`), so ignore them.
- The previous tag is the previous release **on the same line**:
  - mainline release (`1.9.0`): the previous mainline release (`1.8.0`), skipping stable patch
    releases such as `1.7.2`.
  - stable patch release (`1.7.2` on `release-1.7.x`): the previous release on that branch (`1.7.1`,
    or `1.7.0` for the first patch).
- Check the choice with `git merge-base --is-ancestor <previous> <tag>`.

## 2. Gather the changes

```bash
git fetch --tags origin
git log --first-parent --format='%h %an | %s' <previous>..<tag>
gh api repos/rhel-lightspeed/linux-mcp-server/releases/generate-notes \
  -f tag_name=<tag> -f previous_tag_name=<previous> --jq .body
```

The generated notes give each PR's number and author, plus a **New Contributors** section. Some
squash commits have no `(#NNN)` in their subject; map them to their PR with
`gh api repos/rhel-lightspeed/linux-mcp-server/commits/<sha>/pulls --jq '.[] | "\(.number) \(.user.login) \(.title)"'`.

For every PR you might include, read it (`gh pr view <n> --json title,body,author,closingIssuesReferences`)
to understand what changed **for the user**. The commit subject is often written for developers.
For each linked issue that the PR closes, note the issue author (`gh issue view <n> --json author`):
that person **reported** the problem.

## 3. Decide who to credit

Find out who is in the "MCP Maintainers" team:

```bash
gh api orgs/rhel-lightspeed/teams/mcp-maintainers/members --jq '.[].login'
```

If that fails (the token often lacks `read:org`), list the PR authors and issue reporters you
found and ask the user which of them are maintainers. Do not guess.

- **External contributors** (not in MCP Maintainers, and not bots) are **always** credited with
  their `@login`. This includes trivial changes and infrastructure, CI, or docs-only changes that
  would otherwise be left out (see step 4).
- **Reporters**: when a fix closes an issue filed by someone other than the PR author, add
  "reported by @login". Do this especially for external reporters.
- **Maintainers** are credited too, on every included item, small fixes included (the 1.8.0 style).
  The difference is only that maintainers' excluded infrastructure changes stay out.

Every included bullet therefore names the author of each PR it covers (bots excepted).

## 4. Choose what to include

Include changes a user, packager, or deployer would notice: new tools and features, new or changed
config settings, CLI options, behavior changes, breaking changes, bug fixes, raised minimum
versions or other platform support changes, and user-facing docs such as new guides.

Leave out:

- Dependency updates: `chore(deps)`, lockfile refreshes, Konflux/Renovate/MintMaker PRs, even
  `[SECURITY]` ones. This includes PRs that only add or bump a dependency (e.g. "Add requests to the
  gcp extra").
- Infrastructure: `.github/workflows`, CI, functional-test triggers, release-process and branch
  strategy changes, version-scheme pinning, devcontainer, `.konflux/` files.
- Test-only changes, formatting fixes, internal refactors with no visible effect.
- Docs on how to develop or release the project, and small README or link fixes.

**Exception:** a PR from an external contributor is never left out completely. If it would be
excluded, still mention it briefly, for example
`- CI: run functional tests on pull requests from forks (#123, @someone)`, or put several under a
`- Other contributions:` bullet.

If you're not sure whether something counts as user-facing, include it in the draft and flag it to
the user rather than dropping it silently.

## 5. Write the notes

Format (GitHub markdown):

```markdown
## What's Changed

- **<Big feature>** (@author, @author2, #N1, #N2, #N3)
  - <what it does, in a user's terms>
  - <how to configure / use it>
  - See: <docs URL>
- <Smaller change, phrased as what the user gets> (#N, @author)
- Fix <symptom the user saw> (#N, @author, reported by @reporter)

## New Contributors
* @login made their first contribution in https://github.com/rhel-lightspeed/linux-mcp-server/pull/N

**Full Changelog**: https://github.com/rhel-lightspeed/linux-mcp-server/compare/<previous>...<tag>
```

Guidelines:

- **Group related PRs.** A feature built over several PRs becomes one bold bullet that lists all
  their PR numbers and authors. Its sub-bullets summarize the feature as a whole and don't have to
  match the PRs one-to-one. Follow-up PRs that refine a feature in the same release (logging for it,
  docs for it, extra CLI options) go in that group, not in separate bullets.
- **Order**: headline features first, then config/behavior/breaking changes and platform changes,
  then docs, then fixes.
- **Phrase for users**: "Fix using OpenAI models as the Guarded Command Execution Gatekeeper", not
  "use OpenAI-compatible structured output schema". Name config settings and options exactly
  (`LINUX_MCP_HOST_MODE=[local-only,remote-only,any]`). Briefly give the reason when it helps
  ("3.10 is EOL as of 2026-10-01", "to avoid models accidentally running things on localhost").
- **Breaking changes** (a `!` in the commit type, a required parameter, a removed setting, a raised
  minimum version) must be included, and the bullet must make clear what users need to change.
- Link to the published docs (`https://rhel-lightspeed.github.io/linux-mcp-server/...`) for big
  features when a docs page exists. Check that the page exists in `docs/` and `mkdocs.yml`.
- Put the PR references and credits in a parenthetical at the end of the bullet (or after the bold
  title for groups). The order inside it doesn't matter.
- Keep the **New Contributors** section from the generated notes, but remove bots and anyone whose
  only PR was excluded and not credited. Leave the section out if it ends up empty. Always end with
  the **Full Changelog** link.
- Keep it short. Most releases need 5–10 top-level bullets.

## 6. Review and publish

1. Write the draft to a scratch file and show it to the user. Also list every PR you **excluded**
   with a one-word reason (deps / ci / test / internal / docs-dev), and anything you weren't sure
   about, so they can check nothing important was dropped.
2. Apply the user's edits.
3. Only after the user explicitly approves, update the release:
   ```bash
   gh release edit <tag> --notes-file <file>
   ```
   Then check the result with `gh release view <tag>`. Editing the release is public, so never do it
   without approval.

## Examples

These are the notes for 1.8.0 and 1.7.0. They show the grouping, phrasing, and credit style.
1.8.0 is the model for credits.

### 1.8.0

Note what was left out: the release-branch-strategy PRs (#652, #653, #660), CI (#654–#656, #663,
#668, #670, #680, #681, #684), docs on releasing (#682, #683), the `[SECURITY]` dependency bump
(#686), and Renovate PRs. #679 (redaction logging) and #671 (which had no PR number in its commit
subject) are part of the Redaction group.

```markdown
## What's Changed

- **Redaction** (@panyamkeerthana, @owtaylor, #667, #671, #676, #677)
  - Add a simple pattern-based redaction engine for tool output
  - Builtin rules cover a limited set of common credentials
  - Custom rules can be added via a YAML file
  - See: https://rhel-lightspeed.github.io/linux-mcp-server/redaction/
- **Improved logging** (@owtaylor)
  - Make logging from linux-mcp-server more consistent and informative (#623)
  - Suppress INFO level messages from Python dependencies by default (#622)
  - Allow configuring the logging destination (#621)
- Raise minimum Python version to 3.11 (3.10 is EOL as of 2026-10-01) (#685, @owtaylor)
- Request email claims from the Google auth provider, and treat
  email_verified as a boolean, not a string (#666, @alexsmac)
- Fix using OpenAI models as the Guarded Command Execution Gatekeeper (@JazzCort, #647)
- Fix Guarded Command Execution checks when the target user can run some commands
  without a password but not others in /etc/sudoers (#659, @alexsmac)
- Replace deprecated responseSchema with responseFormat for Gemini api (@JazzCort, #649)

## New Contributors
* @alexsmac made their first contribution in https://github.com/rhel-lightspeed/linux-mcp-server/pull/659

**Full Changelog**: https://github.com/rhel-lightspeed/linux-mcp-server/compare/1.7.0...1.8.0
```

### 1.7.0

Three PCP PRs were grouped into one bullet. The two fixes for issues filed by an external user
credit the reporter (they come from the issues that #598 and #599 close). The breaking change #601
explains why it was made.

Two things in 1.7.0 should **not** be copied:
- The fixes #598, #599 and #616 leave out their author, @owtaylor. Today every item credits its
  author, as in 1.8.0.
- "feat(server): support direct TLS termination" (#618) was left out by accident. A new server
  capability like this belongs in the notes.

```markdown
## What's Changed
 * Add tools for [Performance Co-Pilot](https://pcp.io/). (#568, #637, #638, @panyamkeerthana, @owtaylor)
 * Add LINUX_MCP_HOST_MODE=[local-only,remote-only,any] config setting to control where tools may run (#603, @owtaylor)
 * Except for LINUX_MCP_HOST_MODE=local-only, make the hostname parameter mandatory to avoid models accidentally running things on localhost.
   (#601, @owtaylor, reported by @lifetoldme)
 * docs: Add a guide in the documentation for configuring Keycloak as the OAuth2 configuration server (#532, @panyamkeerthana)
 * fix: execute the confirmed script on a mismatch between `validate_script()` `run_script_with_confirmation()` (#598, reported by @pbuchan-rh)
 * fix: pass a static --description to systemd-run, working around bugs in older versions of systemd (#599, reported by @pbuchan-rh)
 * fix: return accurate optional listing metadata (#616)

**Full Changelog**: https://github.com/rhel-lightspeed/linux-mcp-server/compare/1.6.0...1.7.0
```
