#!/usr/bin/env bash
set -euo pipefail

echo "--- Verification Step 1: User Identity ---"
CURRENT_UID=$(id -u)
echo "Running as UID: $CURRENT_UID"
if [ "$CURRENT_UID" -ne 1001 ]; then
  echo "::error::Container must run as UID 1001 (mcp). Found $CURRENT_UID"
  exit 1
fi

echo "--- Verification Step 2: Server Startup Log ---"
linux-mcp-server > startup.log 2>&1 &
SERVER_PID=$!

TIMEOUT=${STARTUP_TIMEOUT:-30s}

timeout "$TIMEOUT" bash -c 'until grep -q "Running Linux MCP Server" startup.log; do sleep 1; done' || {
  echo "::error::Server failed to log 'Running Linux MCP Server' within $TIMEOUT"
  cat startup.log
  kill $SERVER_PID || true
  exit 1
}
echo "Success: Server initialized correctly."
kill $SERVER_PID
