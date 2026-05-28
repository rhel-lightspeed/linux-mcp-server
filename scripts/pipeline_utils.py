"""Shared utilities for CI pipeline scripts that bridge GitLab and GitHub."""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from dataclasses import dataclass


@dataclass
class GitLabAPI:
    project: str
    host: str
    token: str

    @staticmethod
    def from_environment():
        project = os.environ.get("GITLAB_PROJECT", "rhel-lightspeed/mcp/linux-mcp-server")
        host = os.environ.get("GITLAB_HOST", "gitlab.cee.redhat.com")
        token = os.environ.get("GITLAB_TOKEN", "")
        if not token:
            sys.exit("ERROR: GITLAB_TOKEN is required")

        return GitLabAPI(project=project, host=host, token=token)

    def get(self, path):
        """Make an GET request to the GitLab API"""
        encoded_project = urllib.parse.quote(self.project, safe="")
        url = f"https://{self.host}/api/v4/projects/{encoded_project}/{path}"
        headers = {}
        headers["PRIVATE-TOKEN"] = self.token
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            return res


@dataclass
class GitHubAPI:
    repo: str
    token: str

    @staticmethod
    def from_environment():
        repo = os.environ.get("GITHUB_REPO", "rhel-lightspeed/linux-mcp-server")
        token = os.environ.get("GITHUB_STATUS_TOKEN", "")

        return GitHubAPI(repo, token)


def get_mr_info(branch_name, gitlab: GitLabAPI):
    """Look up the GitLab MR for a branch. Returns (iid, web_url)."""
    mrs = gitlab.get(f"merge_requests?source_branch={branch_name}&state=opened")
    if not mrs:
        raise RuntimeError(f"No open MR found for branch {branch_name}")
    return mrs[0]["iid"], mrs[0]["web_url"]


def post_github_status(*, commit_sha, state, context, description, target_url=None, github: GitHubAPI):
    """Post a commit status to GitHub."""
    url = f"https://api.github.com/repos/{github.repo}/statuses/{commit_sha}"
    payload = {"state": state, "context": context, "description": description}
    if target_url:
        payload["target_url"] = target_url
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"token {github.token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req):
        print(f"Posted status: {context} = {state}")
