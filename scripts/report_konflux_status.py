#!/usr/bin/env python3
"""
Poll for Konflux build results and report them as GitHub commit statuses.

After a PR is mirrored to GitLab, Konflux automatically builds the MR and
posts progress comments on it. This script polls those comments and reports
the outcome back to GitHub as a commit status ("konflux / build").

Required environment variables:
  GITHUB_PR_NUMBER    - The GitHub PR number
  GITHUB_COMMIT_SHA   - The commit SHA to post statuses on
  GITHUB_STATUS_TOKEN - GitHub PAT with repo:status scope
  GITLAB_TOKEN        - GitLab access token with read_api scope
  MIRROR_START_TIME   - ISO 8601 UTC timestamp recorded before the mirror push

Optional environment variables:
  GITHUB_REPO           - GitHub repository (default: rhel-lightspeed/linux-mcp-server)
  CI_PROJECT_PATH       - GitLab project path (default: rhel-lightspeed/mcp/linux-mcp-server)
  CI_SERVER_FQDN        - GitLab hostname (default: gitlab.cee.redhat.com)
  CI_SERVER_TLS_CA_FILE - Path to CA certificate for the GitLab server
"""

import os
import re
import sys
import time

from pipeline_utils import get_mr_info
from pipeline_utils import GitHubAPI
from pipeline_utils import GitLabAPI
from pipeline_utils import post_github_status


KONFLUX_PREFIX = "**Konflux Production Internal/linux-mcp-server-pr**"
RUN_NAME_PATTERN = re.compile(r"linux-mcp-server-pr-[a-z0-9]+")
PIPELINE_URL_PATTERN = re.compile(
    r"https://konflux-ui\.apps\.stone-prod-p02\.hjvn\.p1\.openshiftapps\.com"
    r"/ns/[a-z0-9-]+/pipelinerun/linux-mcp-server-pr-[a-z0-9]+"
)

KONFLUX_START_INTERVAL = 30
KONFLUX_START_TIMEOUT = 5 * 60
KONFLUX_RESULT_INTERVAL = 5 * 60
KONFLUX_RESULT_TIMEOUT = 2 * 60 * 60


def get_mr_notes(mr_iid, *, gitlab_api: GitLabAPI):
    """Fetch recent notes from a GitLab MR, newest first."""
    return gitlab_api.get(f"merge_requests/{mr_iid}/notes?sort=desc&order_by=created_at&per_page=20")


def normalize_timestamp(ts):
    """Strip fractional seconds from a GitLab timestamp for comparison."""
    return re.sub(r"\.\d+Z$", "Z", ts)


def find_konflux_notes(notes, after_time):
    """Filter MR notes to Konflux notes created after after_time."""
    result = []
    for note in notes:
        if not note["body"].startswith(KONFLUX_PREFIX):
            continue
        if normalize_timestamp(note["created_at"]) <= after_time:
            continue
        result.append(note)
    return result


def classify_konflux_note(body):
    """Classify a Konflux note as queued/starting/success/failure."""
    if "has been queued" in body:
        return "queued"
    if "Starting Pipelinerun" in body:
        return "starting"
    if "has successfully validated your commit" in body:
        return "success"
    if "has failed" in body:
        return "failure"
    return None


def extract_run_name(body):
    """Extract the PipelineRun name from a Konflux note."""
    match = RUN_NAME_PATTERN.search(body)
    return match.group(0) if match else None


def extract_pipeline_url(body):
    """Extract the full Konflux PipelineRun URL from a note."""
    match = PIPELINE_URL_PATTERN.search(body)
    return match.group(0) if match else None


def poll_for_konflux_start(*, mr_iid, after_time, gitlab: GitLabAPI):
    """Poll MR notes until a Konflux build appears. Returns the run name."""
    deadline = time.monotonic() + KONFLUX_START_TIMEOUT
    while True:
        notes = get_mr_notes(mr_iid, gitlab_api=gitlab)
        for note in find_konflux_notes(notes, after_time):
            run_name = extract_run_name(note["body"])
            if run_name:
                return run_name
        if time.monotonic() >= deadline:
            sys.exit(f"ERROR: Timed out waiting for Konflux build to start ({KONFLUX_START_TIMEOUT / 60:.2g} minutes)")
        print(f"Waiting for Konflux to start... (polling every {KONFLUX_START_INTERVAL}s)")
        time.sleep(KONFLUX_START_INTERVAL)


def poll_for_konflux_result(*, mr_iid, after_time, run_name, gitlab: GitLabAPI):
    """Poll MR notes until the Konflux build completes. Returns (state, url)."""
    deadline = time.monotonic() + KONFLUX_RESULT_TIMEOUT
    while True:
        notes = get_mr_notes(mr_iid, gitlab_api=gitlab)
        for note in find_konflux_notes(notes, after_time):
            if run_name not in note["body"]:
                continue
            kind = classify_konflux_note(note["body"])
            if kind in ("success", "failure"):
                pipeline_url = extract_pipeline_url(note["body"])
                return kind, pipeline_url
        if time.monotonic() >= deadline:
            sys.exit(
                f"ERROR: Timed out waiting for Konflux build {run_name} "
                f"to complete ({KONFLUX_RESULT_TIMEOUT / 3600:.2g} hours)"
            )
        print(f"Konflux build {run_name} in progress... (polling every {KONFLUX_RESULT_INTERVAL / 60:.2g}m)")
        time.sleep(KONFLUX_RESULT_INTERVAL)


def main():
    # optional: GITHUB_REPO / GITHUB_STATUS_TOKEN
    github = GitHubAPI.from_environment()

    # requires: GITLAB_TOKEN, optional: CI_PROJECT_PATH / CI_SERVER_FQDN
    gitlab = GitLabAPI.from_environment()

    pr_number = os.environ.get("GITHUB_PR_NUMBER", "")
    commit_sha = os.environ.get("GITHUB_COMMIT_SHA", "")
    mirror_start_time = os.environ.get("MIRROR_START_TIME", "")

    if not pr_number or not commit_sha:
        sys.exit("ERROR: GITHUB_PR_NUMBER and GITHUB_COMMIT_SHA are required")
    if not github.token:
        sys.exit("ERROR: GITHUB_STATUS_TOKEN is required")
    if not mirror_start_time:
        sys.exit("ERROR: MIRROR_START_TIME is required")

    branch_name = f"github-pr-{pr_number}"

    # Look up the GitLab MR
    print(f"Looking up MR for branch {branch_name}...")
    mr_iid, mr_url = get_mr_info(branch_name, gitlab=gitlab)
    print(f"Found MR !{mr_iid}: {mr_url}")

    # Post initial pending status for Konflux
    post_github_status(
        commit_sha=commit_sha,
        state="pending",
        context="konflux / build",
        description="Waiting for Konflux build to start",
        target_url=mr_url,
        github=github,
    )

    # Poll for Konflux build start
    print("Polling for Konflux build to start...")
    run_name = poll_for_konflux_start(mr_iid=mr_iid, after_time=mirror_start_time, gitlab=gitlab)
    print(f"Konflux build started: {run_name}")

    # Update status to show build is running
    post_github_status(
        commit_sha=commit_sha,
        state="pending",
        context="konflux / build",
        description=f"Build in progress: {run_name}",
        target_url=mr_url,
        github=github,
    )

    # Poll for Konflux build result
    print(f"Polling for Konflux build result ({run_name})...")
    result_state, pipeline_url = poll_for_konflux_result(
        mr_iid=mr_iid, after_time=mirror_start_time, run_name=run_name, gitlab=gitlab
    )
    print(f"Konflux build {result_state}: {pipeline_url}")

    # Post final Konflux status
    if result_state == "success":
        description = "Konflux build succeeded"
    else:
        description = "Konflux build failed"

    post_github_status(
        commit_sha=commit_sha,
        state=result_state,
        context="konflux / build",
        description=description,
        target_url=pipeline_url or mr_url,
        github=github,
    )

    if result_state == "failure":
        print(f"ERROR: Konflux build failed: {pipeline_url}")


if __name__ == "__main__":
    main()
