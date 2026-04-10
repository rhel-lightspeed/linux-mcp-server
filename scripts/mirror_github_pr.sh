#!/bin/bash
# Mirror a GitHub PR to GitLab as a merge request.
#
# This script is designed to run in GitLab CI to create MRs from GitHub PRs
# for internal testing. It fetches the PR metadata from GitHub, pushes the
# commit to a branch in GitLab, and creates a merge request using push options.
#
# Required environment variables:
#   GITHUB_PR_NUMBER  - The GitHub PR number to mirror
#   GITHUB_COMMIT_SHA - The commit SHA to fetch
#   GITLAB_TOKEN      - GitLab access token with 'write_repository' scope
#
# Optional environment variables:
#   GITHUB_REPO    - GitHub repository (default: rhel-lightspeed/linux-mcp-server)
#   GITLAB_PROJECT - GitLab project path (default: rhel-lightspeed/mcp/linux-mcp-server)
#   GITLAB_HOST    - GitLab hostname (default: gitlab.cee.redhat.com)

set -euo pipefail

: "${GITHUB_REPO:=rhel-lightspeed/linux-mcp-server}"
: "${GITLAB_PROJECT:=rhel-lightspeed/mcp/linux-mcp-server}"
: "${GITLAB_HOST:=gitlab.cee.redhat.com}"

if [[ -z "${GITHUB_PR_NUMBER:-}" ]] || [[ -z "${GITHUB_COMMIT_SHA:-}" ]]; then
    echo "ERROR: GITHUB_PR_NUMBER and GITHUB_COMMIT_SHA are required"
    exit 1
fi

if [[ -z "${GITLAB_TOKEN:-}" ]]; then
    echo "ERROR: GITLAB_TOKEN is required"
    exit 1
fi

BRANCH_NAME="github-pr-${GITHUB_PR_NUMBER}"
GITLAB_REMOTE="https://oauth2:${GITLAB_TOKEN}@${GITLAB_HOST}/${GITLAB_PROJECT}.git"

# Fetch PR information from GitHub
echo "Fetching PR #${GITHUB_PR_NUMBER} from GitHub..."
PR_INFO=$(curl -sf "https://api.github.com/repos/${GITHUB_REPO}/pulls/${GITHUB_PR_NUMBER}")

if [[ -z "$PR_INFO" ]]; then
    echo "ERROR: Could not fetch PR #${GITHUB_PR_NUMBER} from GitHub"
    exit 1
fi

PR_TITLE=$(echo "$PR_INFO" | jq -r '.title')
PR_URL=$(echo "$PR_INFO" | jq -r '.html_url')

if [[ "$PR_TITLE" == "null" ]] || [[ -z "$PR_TITLE" ]]; then
    echo "ERROR: PR #${GITHUB_PR_NUMBER} not found or has no title"
    exit 1
fi

echo "PR Title: $PR_TITLE"
echo "PR URL: $PR_URL"

# Clone from GitLab (has shared history), then fetch PR commit from GitHub
echo "Cloning from GitLab..."
git clone "$GITLAB_REMOTE" repo
cd repo

echo "Fetching commit ${GITHUB_COMMIT_SHA:0:7} from GitHub..."
git remote add github "https://github.com/${GITHUB_REPO}.git"
git fetch github "$GITHUB_COMMIT_SHA"
git checkout -b "$BRANCH_NAME" "$GITHUB_COMMIT_SHA"

# Check if branch already exists in GitLab
echo "Checking if branch ${BRANCH_NAME} exists in GitLab..."
if git ls-remote --exit-code origin "refs/heads/${BRANCH_NAME}" >/dev/null 2>&1; then
    # Branch exists - just push to update the MR
    echo "Branch exists, updating..."
    git push -f origin "$BRANCH_NAME"
    echo "Updated branch ${BRANCH_NAME}"
else
    # Branch doesn't exist - create MR with push options
    echo "Creating new branch and MR..."
    MR_DESCRIPTION="This MR mirrors GitHub PR #${GITHUB_PR_NUMBER} for internal testing.\n\n- GitHub PR: ${PR_URL}\n- Commit: ${GITHUB_COMMIT_SHA}"

    git push origin "$BRANCH_NAME" \
        -o merge_request.create \
        -o merge_request.target=main \
        -o "merge_request.title=${PR_TITLE}" \
        -o "merge_request.description=${MR_DESCRIPTION}" \
        -o merge_request.remove_source_branch

    echo "Created MR for branch ${BRANCH_NAME}"
fi
