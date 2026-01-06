#!/usr/bin/env bash
set -euo pipefail

echo "--- Verification: Stdout Hygiene ---"

# Start server and capture the VERY FIRST line of stdout
# MCP spec requires JSON-RPC on stdout and logs on stderr
FIRST_LINE=$(echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | linux-mcp-server 2>/dev/null | head -n 1)

# Ensure the first line is valid JSON-RPC 2.0 using jq
if ! echo "$FIRST_LINE" | jq -e '.jsonrpc == "2.0"' > /dev/null; then
  echo "::error::Hygiene Failed: Stdout is polluted with non-JSON text or invalid JSON-RPC."
  echo "Found: $FIRST_LINE"
  exit 1
fi

echo "✅ Hygiene: Stdout is clean."
