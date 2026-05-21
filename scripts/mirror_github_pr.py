#!/usr/bin/env python3
"""
Mirror a GitHub PR to GitLab as a merge request.

This script is designed to run in GitLab CI to create MRs from GitHub PRs
for internal testing. It fetches the PR metadata from GitHub, pushes the
commit to a branch in GitLab, and creates a merge request using push options.

Required environment variables:
  GITHUB_PR_NUMBER  - The GitHub PR number to mirror
  GITHUB_COMMIT_SHA - The commit SHA to fetch
  GITLAB_TOKEN      - GitLab access token with 'write_repository' scope

Optional environment variables:
  GITHUB_REPO          - GitHub repository (default: rhel-lightspeed/linux-mcp-server)
  GITLAB_PROJECT       - GitLab project path (default: rhel-lightspeed/mcp/linux-mcp-server)
  GITLAB_HOST          - GitLab hostname (default: gitlab.cee.redhat.com)
  GITHUB_STATUS_TOKEN  - GitHub PAT for posting commit statuses (if unset, status posting is skipped)
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from pipeline_utils import get_mr_info
from pipeline_utils import GitHubAPI
from pipeline_utils import GitLabAPI
from pipeline_utils import post_github_status


def run_git(*args, cwd=None):
    """Run a git command, raising on failure."""
    subprocess.run(["git", *args], check=True, cwd=cwd)


def branch_exists(branch_name, *, cwd):
    """Check if a branch exists on the GitLab remote."""
    result = subprocess.run(
        ["git", "ls-remote", "--exit-code", "origin", f"refs/heads/{branch_name}"],
        capture_output=True,
        cwd=cwd,
    )
    return result.returncode == 0


def fetch_pr_info(pr_number, *, github: GitHubAPI):
    """Fetch PR metadata from the GitHub API."""
    url = f"https://api.github.com/repos/{github.repo}/pulls/{pr_number}"
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        sys.exit(f"ERROR: Could not fetch PR #{pr_number} from GitHub (HTTP {e.code})")
    except urllib.error.URLError as e:
        sys.exit(f"ERROR: Could not connect to GitHub API: {e.reason}")


def main():
    # optional: GITHUB_REPO / GITHUB_STATUS_TOKEN
    github = GitHubAPI.from_environment()

    # requires: GITLAB_TOKEN, optional: GITLAB_PROJECT / GITLAB_HOST
    gitlab = GitLabAPI.from_environment()

    pr_number = os.environ.get("GITHUB_PR_NUMBER", "")
    commit_sha = os.environ.get("GITHUB_COMMIT_SHA", "")
    if not pr_number or not commit_sha:
        sys.exit("ERROR: GITHUB_PR_NUMBER and GITHUB_COMMIT_SHA are required")

    branch_name = f"github-pr-{pr_number}"
    gitlab_remote = f"https://oauth2:{gitlab.token}@{gitlab.host}/{gitlab.project}.git"

    # Fetch PR information from GitHub
    print(f"Fetching PR #{pr_number} from GitHub...")
    pr_info = fetch_pr_info(pr_number, github=github)

    pr_title = pr_info.get("title")
    pr_url = pr_info.get("html_url")

    if not pr_title:
        sys.exit(f"ERROR: PR #{pr_number} not found or has no title")

    print(f"PR Title: {pr_title}")
    print(f"PR URL: {pr_url}")

    # Clone from GitLab (has shared history), then fetch PR commit from GitHub
    print("Cloning from GitLab...")
    run_git("clone", gitlab_remote, "repo")

    print(f"Fetching commit {commit_sha[:7]} from GitHub...")
    run_git("remote", "add", "github", f"https://github.com/{github.repo}.git", cwd="repo")
    run_git("fetch", "github", commit_sha, cwd="repo")
    run_git("checkout", "-b", branch_name, commit_sha, cwd="repo")

    # Check if branch already exists in GitLab
    print(f"Checking if branch {branch_name} exists in GitLab...")
    if branch_exists(branch_name, cwd="repo"):
        # Branch exists - just push to update the MR
        print("Branch exists, updating...")
        run_git("push", "-f", "origin", branch_name, cwd="repo")
        print(f"Updated branch {branch_name}")
    else:
        # Branch doesn't exist - create MR with push options
        print("Creating new branch and MR...")
        mr_description = (
            f"This MR mirrors GitHub PR #{pr_number} for internal testing."
            f"\\n\\n- GitHub PR: {pr_url}"
            f"\\n- Commit: {commit_sha}"
        )

        run_git(
            "push",
            "origin",
            branch_name,
            "-o",
            "merge_request.create",
            "-o",
            "merge_request.target=main",
            "-o",
            f"merge_request.title={pr_title}",
            "-o",
            f"merge_request.description={mr_description}",
            "-o",
            "merge_request.remove_source_branch",
            cwd="repo",
        )
        print(f"Created MR for branch {branch_name}")

    # Post success status back to GitHub
    if github.token:
        _, mr_url = get_mr_info(branch_name, gitlab=gitlab)
        post_github_status(
            commit_sha=commit_sha,
            state="success",
            context="gitlab / mirror",
            description="Mirrored to internal GitLab",
            target_url=mr_url,
            github=github,
        )
    else:
        print("GITHUB_STATUS_TOKEN not set, skipping GitHub status update")


if __name__ == "__main__":
    main()
