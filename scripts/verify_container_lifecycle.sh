#!/usr/bin/env bash
set -euo pipefail

echo "--- Verification Step 1: Sidecar Accessibility ---"
timeout 15s bash -c 'until nc -z localhost 8080; do sleep 1; done' || {
  echo "::error::Server sidecar failed to listen on port 8080"
  exit 1
}

echo "--- Verification Step 2: Handshake Probe ---"
if echo '{"jsonrpc":"2.0","id":1,"method":"ping"}' | nc -w 5 localhost 8080 | grep -q "2.0"; then
  echo "Success: Server is responding over the network."
else
  echo "::error::Server did not respond to ping."
  exit 1
fi
