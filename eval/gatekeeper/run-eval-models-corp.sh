#!/usr/bin/env bash

# Script: run-eval-models-corp.sh
# Purpose: Executes run-eval.py using models hosted by the internal Red Hat model platform models.corp.redhat.com.
#
# Usage:
#   MODEL=<model_id> OPENAI_API_KEY=<key> ./run-eval-models-corp.sh <testcase_path>
#
# Environment Variables:
#   MODEL           The model ID (see: https://gitlab.cee.redhat.com/models-corp/user-documentation/-/tree/main/models)
#   OPENAI_API_KEY  The API key from the internal Red Hat model platform.
#
# Example:
#   MODEL=openai/gpt-oss-20b OPENAI_API_KEY=... ./run-eval-models-corp.sh testcases/crafted/bad-description.yaml

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

get_MC_base_url() {
    local model="$1"
    local model_name
    local suffix
    local url_prefix

    if [[ "$model" == gemini* ]]; then
        model_name="gemini"
        suffix="v1beta/openai"
    else
        model_name="${model#*/}"
        model_name="${model_name//./-}"
        suffix="v1"
    fi

    url_prefix="https://${model_name}--apicast-production.apps.int.stc.ai.prod.us-east-1.aws.paas.redhat.com:443"
    printf "%s/%s\n" "$url_prefix" "$suffix"
}

[[ -z "${MODEL}" ]] && echo "$MODEL must be set" && exit 1
export LINUX_MCP_GATEKEEPER_MODEL
LINUX_MCP_GATEKEEPER_MODEL="openai/$MODEL"
export OPENAI_API_BASE
OPENAI_API_BASE="$(get_MC_base_url "$MODEL")"

exec uv run --project "$REPO_ROOT" python "$SCRIPT_DIR/run-eval.py" "$@"
