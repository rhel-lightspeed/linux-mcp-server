#!/bin/bash
# Script to publish the MCP server to the Model Context Protocol registry
# This script is designed to run in GitHub Actions but can be tested locally

set -euo pipefail

# Configuration: Default mcp-publisher version (can be overridden via environment variable)
MCP_PUBLISHER_VERSION="${MCP_PUBLISHER_VERSION:-v1.4.0}"
# Extract version from git tag (removes 'refs/tags/v' prefix)
VERSION="${GITHUB_REF#refs/tags/v}"

# Validate required environment variables
if [[ -z "${VERSION:-}" ]]; then
  echo "Error: GITHUB_REF environment variable is required" >&2
  echo "This should be set automatically in GitHub Actions or manually for local testing" >&2
  exit 1
fi

echo "Publishing version: ${VERSION}"

# Determine platform-specific binary name
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
DOWNLOAD_URL="https://github.com/modelcontextprotocol/registry/releases/download/${MCP_PUBLISHER_VERSION}/mcp-publisher_${OS}_${ARCH}.tar.gz"

echo "Downloading mcp-publisher ${MCP_PUBLISHER_VERSION} from ${DOWNLOAD_URL}"

# Download and extract mcp-publisher binary
if ! curl -fL "${DOWNLOAD_URL}" | tar xz mcp-publisher; then
  echo "Error: Failed to download or extract mcp-publisher" >&2
  echo "URL: ${DOWNLOAD_URL}" >&2
  exit 1
fi

# Verify the binary was extracted
if [[ ! -f ./mcp-publisher ]]; then
  echo "Error: mcp-publisher binary not found after extraction" >&2
  exit 1
fi

chmod +x ./mcp-publisher

echo "Authenticating to MCP Registry via GitHub OIDC"
# Authenticate using GitHub OIDC (requires id-token: write permission)
if ! ./mcp-publisher login github-oidc; then
  echo "Error: Failed to authenticate to MCP Registry" >&2
  exit 1
fi

echo "Updating version in server.json"
# Update all occurrences of "version" in the server.json file
# The ".." will walk the JSON tree recursively
if ! jq --arg version "${VERSION}" '(.. | .version?) |= $version' server.json > server.tmp; then
  echo "Error: Failed to update server.json with jq" >&2
  exit 1
fi

mv server.tmp server.json

echo "Publishing server to MCP Registry"
# Publish the server to the registry
if ! ./mcp-publisher publish; then
  echo "Error: Failed to publish to MCP Registry" >&2
  exit 1
fi

echo "Successfully published version ${VERSION} to MCP Registry"

