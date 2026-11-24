# CI Hardening

Rules for GitHub Actions workflows in this repository. Read this before adding or changing
anything under `.github/workflows/`.

The workflows run third-party code all the time: installing dependencies, building sdists, running
tests. Most of the rules here are about making sure that code can't reach a credential, or anything
that later runs with a credential.

## The cache

GitHub Actions caches are scoped by branch. Every branch and tag can restore an entry saved from the
default branch. Runs on `main` - scheduled, pushed, or dispatched there - save into that scope.

A job's cache token isn't only usable by the cache actions. Code running anywhere in a job can get
hold of it, then save entries under whatever keys it likes, and even fill the cache until the
legitimate entries are evicted. So any job that runs untrusted code in the default branch's scope can
poison what a release or deploy job restores later. [The Monsters in Your Build Cache][monsters]
describes how this can be used by an attacker to escalate privileges.

The most effective guard against this is the [`cache-mode`][cache-mode] workflow key. It limits
the token itself:

| `cache-mode` | Restore | Save |
| ------------ | ------- | ---- |
| `read`       | Yes     | No   |
| `write`      | Yes     | Yes  |
| `write-only` | No      | Yes  |
| `none`       | No      | No   |

`cache-mode` can be set for the whole workflow or for a single job, and a job-level value wins. If
it's left out, trusted triggers get `write` and low-trust triggers (`pull_request_target`,
`workflow_run`, `issue_comment`, ...) get `read`.

### Rule 1: unreviewed code gets a read-only token and a read-only cache

A job running code that hasn't been reviewed must not hold a write-capable token, and must not be
able to save to the cache. That includes:

- `uv lock`, since resolving can build sdists
- `make requirements-lock` (slushy-build compiles sdists)
- installing or testing against a freshly resolved lock file
- installing without the lock file (`pip install`, `uvx`, `uv tool run`)

`uv sync --locked` against a lock file that's already on the branch is fine. Those are the
dependencies we ship and trust.

Code from a pull request is a special case: GitHub gives fork PRs a read-only token, and a
`pull_request` run can only save to the PR's own cache scope, which nothing outside that PR restores.

A workflow running such a job:

1. Sets `permissions: contents: read` and `cache-mode: read` together at workflow level, under one
   comment saying what untrusted code it runs. A job added later then inherits both. A job that
   needs more, such as one that pushes or files issues, grants it at job level and runs no
   third-party code (see [Other rules](#other-rules)).
2. Passes `save-cache: false` to setup-uv. This isn't a security control, but it stops setup-uv
   from trying a save the token won't allow.

### Rule 2: anything that publishes, deploys or holds credentials gets `cache-mode: none`

This covers workflows that publish (PyPI, the MCP registry, release assets), deploy (GitHub Pages),
hold an environment's or GitHub App's credentials, or mint OIDC tokens. Set `cache-mode: none` for
the whole workflow, and pass `enable-cache: false` to any setup-uv step. Where only one job holds
the credential, as with the `coverage` job in `ci.yml`, set it on that job instead.

Base this on what a job _produces_, not only on whether it's bound to an environment. The
`build-package` job in `build-publish.yml` has no environment and no credentials, but the wheel it
builds is what gets published. If it restored a poisoned cache, the backdoor would ship.

This is an extra safety measure to limit the effects of any cache poisoning that slips through.
Release and deploy runs are rare, so the cache saves them almost nothing anyway.

### Everything else

Ordinary CI (`ci.yml`) keeps the default. It's what actually benefits from the cache, and it only
installs from the lock file. On `main` it runs nothing that hasn't been reviewed; on a pull request
it runs the PR's code, but that can't reach the default branch's cache (see above).

## OIDC

Prefer OIDC to a stored secret where the service supports it. There is no long-lived credential to
leak or rotate, and each token expires within minutes.

But an OIDC token is only as strong as the checks made by the service that receives it. Any
workflow in this repository can get one, for any audience it asks for, by adding
`id-token: write`. That includes workflows on a pull request branch pushed to this repository (fork
PRs never get one). GitHub doesn't restrict this by branch, environment or reviewer, and nothing on
our side can. So anyone with write access can mint a token whose `repository`, `repository_owner`,
`aud` and workflow file name match those of our real workflows. What they can't fake are the claims
GitHub derives from protections they can't get past:

- **`environment`**, if the environment's deployment rules only allow protected branches or tags.
  A PR branch can name any environment, but GitHub won't start the job. An environment without
  deployment rules proves nothing.
- **`ref`**, if only protected processes can create or update that ref.

A service that checks neither trusts everyone with write access as much as the release process.
Only use OIDC against such a service where a forged upload costs little. Codecov is one: it checks
only `repository`, so the `coverage` job in `ci.yml` uses OIDC to keep out fork PRs, not
collaborators. Anyone with write access can forge coverage, whatever our workflows do.

For anything that matters, configure the service to require one of those claims. PyPI trusted
publishing shows the right setup: the trusted publisher names the repository, the workflow file and
the environment. The job publishing to PyPI is bound to that environment, and the environment's
deployment rules allow only the protected release tags. The workflow file alone isn't enough,
because a PR branch can edit it.

## Other rules

The workflows already follow these, and their comments explain the details.

- **Keep untrusted code and credentials in separate jobs.** The job that runs third-party code gets
  `contents: read` and no secrets. It hands its result (a patch, a lock file) to a separate job
  that runs only first-party code and holds the write credential. See `security-updates.yml`
  (`fix` → `pr`), `canary.yml` (`test` → `report`) and `ci.yml` (`tests` → `coverage`).
- **`persist-credentials: false`** on any checkout that's followed by untrusted code, so the token
  isn't left in `.git/config`.
- **Use `workflow_run` when a credential is needed after a push.** An `on: push` workflow runs the
  copy of itself from the pushed ref, which may never have been reviewed. A `workflow_run` workflow
  always runs the copy from the default branch. See `sync-post-release-trigger.yml`.
- **Never `${{ }}` untrusted values into `run:` scripts.** Pass them through `env:` and quote them
  in the shell. Branch names, PR titles and advisory feed data all count as untrusted.
- **Pin actions to a full commit SHA**, with the version in a trailing comment.
- **Give `permissions:` at workflow level as `contents: read`** (or `{}`), and grant more only in
  the job that needs it. This is good practice everywhere, and required for workflows that run
  untrusted code (Rule 1).

[monsters]: https://adnanthekhan.com/2024/05/06/the-monsters-in-your-build-cache-github-actions-cache-poisoning/
[cache-mode]: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#cache-mode
