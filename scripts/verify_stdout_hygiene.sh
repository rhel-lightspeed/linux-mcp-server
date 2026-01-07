#!/usr/bin/env bash
set -euo pipefail

echo "--- Verification: Stdout Hygiene ---"

# --- Wait for Server to be Ready ---
MAX_RETRIES=15
COUNT=0
echo "Waiting for sidecar on localhost:8080..."
until nc -z localhost 8080 || [ $COUNT -eq $MAX_RETRIES ]; do
  sleep 1
  COUNT=$((COUNT + 1))
done

if [ $COUNT -eq $MAX_RETRIES ]; then
  echo "::error::Sidecar never became available on port 8080"
  exit 1
fi
# -----------------------------------

# Capture the VERY FIRST line returned by the network socket.
FIRST_LINE=$( (echo '{"jsonrpc":"2.0","id":1,"method":"ping"}'; sleep 1) | nc -w 5 localhost 8080 | head -n 1)

# Ensure the first line is valid JSON-RPC 2.0 using jq
if ! echo "$FIRST_LINE" | jq -e '.jsonrpc == "2.0"' > /dev/null; then
  echo "::error::Hygiene Failed: Stdout is polluted with non-JSON text or invalid JSON-RPC."
  echo "Found: $FIRST_LINE"
  exit 1
fi

echo "✅ Hygiene: Stdout is clean."
