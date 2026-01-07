#!/usr/bin/env bash
set -euo pipefail

echo "--- Verification: MCP Handshake ---"

INIT_REQ='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"QA-Test","version":"1.0"}}}'

RESPONSE=$(echo "$INIT_REQ" | nc -w 5 localhost 8080 | grep "capabilities" || true)

if [[ -z "$RESPONSE" ]]; then
  echo "::error::Server did not return a valid MCP capability response."
  exit 1
fi

echo "✅ Handshake: Success."
