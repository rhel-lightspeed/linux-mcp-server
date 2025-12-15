#!/bin/bash
#
# Wrapper script to run linux-mcp-server in a container via podman.
# Use this in AI agent MCP configs for a cleaner setup.
#
# Environment variables (matching linux-mcp-server official env vars):
# See: https://github.com/rhel-lightspeed/linux-mcp-server
#
# Additional env vars for container configuration:
#   MCP_CONTAINER_IMAGE     - (optional) Container image to use
#
# Example AI agent config:
#   {
#     "mcpServers": {
#       "linux-mcp-server": {
#         "command": "/path/to/linux-mcp-container.sh",
#         "env": {
#           "LINUX_MCP_USER": "root",
#           "LINUX_MCP_SSH_KEY_PATH": "/home/user/.ssh/id_rsa",
#           "LINUX_MCP_LOG_LEVEL": "DEBUG"
#         }
#       }
#     }
#   }
#

set -e

# Defaults
SSH_KEY="${LINUX_MCP_SSH_KEY_PATH:-$HOME/.ssh/id_rsa}"
IMAGE="${MCP_CONTAINER_IMAGE:-quay.io/redhat-services-prod/rhel-lightspeed-tenant/linux-mcp-server:latest}"
LOGS_DIR="$HOME/.local/share/linux-mcp-server/logs"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

# Build podman command
PODMAN_ARGS=(
    run --rm -i
    --userns "keep-id:uid=1001,gid=0"
    -v "$SSH_KEY:/var/lib/mcp/.ssh/id_rsa:ro,Z"
    -v "$LOGS_DIR:/var/lib/mcp/.local/share/linux-mcp-server/logs:rw,Z"
)

# Pass through all linux-mcp-server environment variables
[[ -n "$LINUX_MCP_USER" ]] && PODMAN_ARGS+=(-e "LINUX_MCP_USER=$LINUX_MCP_USER")
[[ -n "$LINUX_MCP_KEY_PASSPHRASE" ]] && PODMAN_ARGS+=(-e "LINUX_MCP_KEY_PASSPHRASE=$LINUX_MCP_KEY_PASSPHRASE")
[[ -n "$LINUX_MCP_LOG_LEVEL" ]] && PODMAN_ARGS+=(-e "LINUX_MCP_LOG_LEVEL=$LINUX_MCP_LOG_LEVEL")

PODMAN_ARGS+=("$IMAGE")

exec podman "${PODMAN_ARGS[@]}"
