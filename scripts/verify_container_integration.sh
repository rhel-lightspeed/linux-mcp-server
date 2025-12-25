#!/bin/bash
set -e

# Reusable startup verification function
verify_server_startup() {
  local start_command="$1"
  local log_file="server_output.log"

  echo "Verifying Container Wrapper server startup..."
  rm -f "$log_file"

  # Start the wrapper script
  eval "$start_command" &> "$log_file" &
  SERVER_PID=$!

  # Wait for the specific MCP startup message
  if timeout 15s grep -q "Running Linux MCP Server" <(tail -f "$log_file"); then
    echo "Success: Container successfully initialized and logged startup message."
    kill $SERVER_PID 2>/dev/null || true
    return 0
  else
    echo "::error::Container failed to start within 15 seconds."
    echo "=== Server Logs ==="
    cat "$log_file"
    kill $SERVER_PID 2>/dev/null || true
    exit 1
  fi
}

# 1. Setup Environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER_PATH="$SCRIPT_DIR/linux-mcp-container.sh"

# 2. Integration Setup: Handle volume permissions
LOGS_DIR="$HOME/.local/share/linux-mcp-server/logs"
mkdir -p "$LOGS_DIR"
chmod -R 777 "$LOGS_DIR"

# 3. Setup Dummy SSH Key
export LINUX_MCP_SSH_KEY_PATH="/tmp/id_rsa_test"
touch "$LINUX_MCP_SSH_KEY_PATH"
chmod 600 "$LINUX_MCP_SSH_KEY_PATH"

# 4. Execute Verification
chmod +x "$WRAPPER_PATH"
verify_server_startup "$WRAPPER_PATH"
