#!/bin/bash
set -e

# Function to verify server startup
# Arguments:
#   $1: The command to start the server
#   $2: Human-readable name of the method for logging
verify_server_startup() {
  local start_command="$1"
  local method_name="$2"
  local log_file="server_output.log"

  echo "Verifying $method_name server startup..."

  # clear previous log if exists
  rm -f "$log_file"

  # Start the server command in the background
  eval "$start_command" &> "$log_file" &
  SERVER_PID=$!

  # Wait for log message
  if timeout 10s grep -q "Running Linux MCP Server" <(tail -f "$log_file"); then
    echo "$method_name server successfully initialized and logged startup message."
    kill $SERVER_PID
    exit 0
  else
    echo "::error::$method_name server failed to start within 10 seconds."
    echo "=== Server Logs ==="
    cat "$log_file"
    echo "==================="

    # Ensure we kill the background process if it's still running
    kill $SERVER_PID || true
    exit 1
  fi
}

# Main logic routing based on the METHOD environment variable
case "$METHOD" in
  "pip_user")
    echo "Starting pip --user installation QA..."
    pip install . --user
    verify_server_startup "$HOME/.local/bin/linux-mcp-server" "pip --user"
    ;;

  "uvx_run")
    verify_server_startup "uvx linux-mcp-server" "uvx run"
    ;;

  "uv_tool_run")
    echo "Starting uv tool run installation QA..."
    uv tool install linux-mcp-server
    verify_server_startup "uv tool run linux-mcp-server" "uv tool run"
    ;;

  *)
    echo "::error::Unknown method: $METHOD"
    exit 1
    ;;
esac
