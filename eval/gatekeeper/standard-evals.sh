#!/usr/bin/env bash
#
# Run the gatekeeper eval suite against a specific model/provider combination.
#
# Configures provider-specific authentication, gatekeeper env vars, reasoning
# effort, and cost overrides, then delegates to run-eval.py.
#
# Usage:
#   standard-evals.sh [--no-save] [--variant=NAME] <MODEL>[:<REASONING_EFFORT>,<QUANTIZATION>][@PROVIDER]
#
# The argument is matched against a built-in list of known model/reasoning/
# provider combinations. Partial matches are accepted (e.g. just a model
# name), as long as they resolve to exactly one entry.
#
# Required environment variables depend on the provider:
#   anthropic   — ANTHROPIC_API_KEY
#   vertex_ai   — VERTEXAI_PROJECT (+ Application Default Credentials)
#   models_corp — OPENAI_API_KEY
#   openrouter  — OPENROUTER_API_KEY

set -euo pipefail

LLAMA_PID=""

cleanup() {
    if [[ -n "$LLAMA_PID" ]]; then
        echo "Stopping llama-server (PID $LLAMA_PID)..."
        kill "$LLAMA_PID" 2>/dev/null || true
        wait "$LLAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ALL_MODELS=(
    "claude-opus-4-6:none@vertex_ai"
    "claude-opus-4-6:none@anthropic"
    "claude-opus-4-6:high@vertex_ai"
    "claude-opus-4-6:high@anthropic"
    "claude-sonnet-4-6:none@vertex_ai"
    "claude-sonnet-4-6:none@anthropic"
    "claude-haiku-4-5:none@vertex_ai"
    "claude-haiku-4-5:none@anthropic"
    "gemini-3.1-flash-lite-preview:minimal@vertex_ai"
    "gemini-3.1-pro-preview:low@vertex_ai"
    "gemini-3.1-pro-preview:high@vertex_ai"
    "gemma-4-26b-a4b-it:none@vertex_ai"
    "gemma-4-26b-a4b-it:none,bf16@openrouter"
    "gemma-4-26b-a4b-it:none,q4_k_m@llama_cpp"
    "gemma-4-31b-it:none,bf16e@openrouter"
    "gpt-5.4:none@openrouter"
    "gpt-5.4:high@openrouter"
    "gpt-oss-20b:low,fp4@openrouter"
    "gpt-oss-20b:low@models_corp"
    "gpt-oss-20b:low@vertex_ai"
    "gpt-oss-120b:low,fp4@openrouter"
    "gpt-oss-120b:low@vertex_ai"
    "granite-4.0-h-small:none@models_corp"
    "granite-4.0-h-small:none,q4_k_m@llama_cpp"
    "granite-4.1-8b:none@models_corp"
    "granite-4.1-8b:none,q4_k_m@llama_cpp"
    "granite-4.1-8b:none,bf16@openrouter"
    "qwen3.5-122b-a10b:none@openrouter"
    "qwen3.5-27b:none@openrouter"
    "qwen3.5-35b-a3b:none@openrouter"
    "qwen3.5-35b-a3b:none,q4_k_m@llama_cpp"
    "qwen3.5-9b:none@openrouter"
    "qwen3.5-9b:none,q4_k_m@llama_cpp"
)

# Reasoning notes:
# claude: sonnet and opus 4.6 and newer use adaptive thinking -
#    https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking
#    thinking defaults to off.
# gemini-3.1-pro-preview: default is high (https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/thinking)
# gpt-oss-*: default is medium (https://huggingface.co/openai/gpt-oss-120b/blob/main/chat_template.jinja)
# qwen3.5/qwen3.6: No reasoning effort control, just on/off. We disable it by
#     setting template arguments. Things work very badly with reasoning on.

save=true
variant=""
output_dir="${SCRIPT_DIR}/data"

while [[ "${1+set}" != "" ]] ; do
    case "$1" in
        --no-save) save=false; shift ;;
        --variant=*) variant="${1#--variant=}"; shift ;;
        --output-dir=*) output_dir="${1#--output-dir=}"; shift ;;
        *) break ;;
    esac
done

usage() {
    echo "Usage: standard-evals.sh [--no-save] [--variant=NAME] [--output-dir=DIR] <MODEL>[:<REASONING_EFFORT>,<QUANTIZATION>][@PROVIDER]"
    echo "Supported combinations:"
    for m_r_p in "${ALL_MODELS[@]}" ; do
        echo "    $m_r_p"
    done
    exit 1
}

if [[ "${1+set}" = "" || "$1" = --* ]] ; then
    usage
fi

# Parses a model string and populates an associative array (via nameref)
parse_model() {
    local model_string="$1"
    local -n res_ref="$2"

    word="[a-zA-Z0-9._-]+"
    # MODEL[:FLAG{,FLAG}][@PROVIDER]
    local regex="^($word)(:($word(,$word)*))?(@($word))?$"

    if [[ ! $model_string =~ $regex ]]; then
        echo "Can't parse model string '$model_string'" >&2
        exit 1
    fi

    res_ref["model"]="${BASH_REMATCH[1]}"
    res_ref["provider"]="${BASH_REMATCH[6]}"
    res_ref["reasoning"]=""
    res_ref["quantization"]=""

    local flags="${BASH_REMATCH[3]}"
    if [[ -n "$flags" ]]; then
        IFS=',' read -ra flag_arr <<< "$flags"
        for flag in "${flag_arr[@]}"; do
            if [[ "$flag" =~ [0-9] ]]; then
                res_ref["quantization"]="$flag"
            else
                # shellcheck disable=SC2034
                res_ref["reasoning"]="$flag"
            fi
        done
    fi
}

declare -A spec
parse_model "$1" spec

candidate_matches_spec() {
    local -n candidate="$1"

    for k in model provider reasoning quantization; do
        # If spec has a value, the candidate must match it exactly
        if [[ -n "${spec[$k]}" && "${spec[$k]}" != "${candidate[$k]}" ]]; then
            return 1
        fi
    done

    return 0
}

matched_raw=()
for cand_str in "${ALL_MODELS[@]}"; do
    # shellcheck disable=SC2034
    declare -A cand_parsed
    parse_model "$cand_str" cand_parsed

    if candidate_matches_spec cand_parsed; then
        matched_raw+=("$cand_str")
    fi
done

if [[ ${#matched_raw[@]} -eq 0 ]]; then
    echo "No match for '$1'" >&2
    usage
elif [[ ${#matched_raw[@]} -gt 1 ]]; then
    echo "Multiple matches for '$1': ${matched_raw[*]}" >&2
    usage
fi

declare -A final_match
parse_model "${matched_raw[0]}" final_match

model="${final_match["model"]}"
reasoning="${final_match["reasoning"]}"
quantization="${final_match["quantization"]}"
provider="${final_match["provider"]}"

echo "Provider: $provider"
[[ -n $quantization ]] && echo "Quantization: $quantization"
echo "Reasoning effort: $reasoning"
echo "Model: $model"
[[ -n $variant ]] && echo "Variant: $variant"

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

start_llama_server() {
    echo "Starting: llama-server $*"
    llama-server "$@" > llama_cpp.log 2>&1 &
    LLAMA_PID=$!

    local timeout=120
    local elapsed=0
    echo "Waiting for llama-server to be ready..."
    while (( elapsed < timeout )); do
        if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
            echo "llama-server ready after ${elapsed}s"
            return 0
        fi
        sleep 2
        (( elapsed += 2 ))
    done

    echo "llama-server failed to become ready within ${timeout}s (see llama_cpp.log)" >&2
    exit 1
}

uv_args=()
max_parallel=10

LINUX_MCP_GATEKEEPER__REASONING_EFFORT=$reasoning
LINUX_MCP_GATEKEEPER__COST=""

case "$model" in
    claude-*)
        if [[ $reasoning == "none" ]] ; then
            LINUX_MCP_GATEKEEPER__REASONING_EFFORT=
        else
            echo "Setting T=1, as required for thinking with Claude models"
            LINUX_MCP_GATEKEEPER__TEMPERATURE=1
            export LINUX_MCP_GATEKEEPER__TEMPERATURE
        fi
        ;;
    gemma-4-31b)
        # Enforcing JSON output causes the model to generate infinite
        # repeating toke, but it does well at generating valid output
        # normally
        LINUX_MCP_GATEKEEPER__STRUCTURED_OUTPUT=false
        export LINUX_MCP_GATEKEEPER__STRUCTURED_OUTPUT
        ;;
    granite-4*)
        if [[ $reasoning == "none" ]] ; then
            # granite-4 doesn't support thinking in its normal chat template,
            # avoid api errors trying to pass reasoning_effort
            LINUX_MCP_GATEKEEPER__REASONING_EFFORT=
        fi
        ;;
esac

case "$provider" in
    anthropic)
        : "${ANTHROPIC_API_KEY:?'api key must be set'}"
        LINUX_MCP_GATEKEEPER__PROVIDER=anthropic
        LINUX_MCP_GATEKEEPER__BACKEND=direct
        LINUX_MCP_GATEKEEPER__MODEL="$model"
        ;;
    llama_cpp)
        OPENAI_API_KEY=tasty
        LINUX_MCP_GATEKEEPER__PROVIDER=openai
        LINUX_MCP_GATEKEEPER__BACKEND=direct
        LINUX_MCP_GATEKEEPER__BASE_URL=http://localhost:8080/v1
        # gemma-4 and qwen3.5 support enable_thinking via chat_template_kwargs; granite-4 has no control
        case "$reasoning" in
            none)
                LINUX_MCP_GATEKEEPER__TEMPLATE_KWARGS='{ "enable_thinking": false }'
                ;;
            default)
                LINUX_MCP_GATEKEEPER__TEMPLATE_KWARGS='{ "enable_thinking": true }'
                ;;
        esac
        export OPENAI_API_KEY
        export LINUX_MCP_GATEKEEPER__BASE_URL
        max_parallel=1
        quant_tag="${quantization^^}"
        case "$model" in
            gemma-4-26b-a4b-it)
                LINUX_MCP_GATEKEEPER__MODEL=google/gemma-4-26b-a4b
                hf_repo=ggml-org/gemma-4-26B-A4B-it-GGUF
                ;;
            granite-4.0-h-small)
                LINUX_MCP_GATEKEEPER__MODEL=ibm-granite/granite-4.0-h-small
                hf_repo=ibm-granite/granite-4.0-h-small-GGUF
                ;;
            granite-4.1-8b)
                LINUX_MCP_GATEKEEPER__MODEL=ibm-granite/granite-4.1-8b
                hf_repo=ibm-granite/granite-4.1-8b-GGUF
                ;;
            qwen3.5-35b-a3b)
                LINUX_MCP_GATEKEEPER__MODEL=qwen/qwen3.5-35b-a3b
                hf_repo=unsloth/Qwen3.5-35B-A3B-GGUF
                ;;
            qwen3.5-9b)
                LINUX_MCP_GATEKEEPER__MODEL=qwen/qwen3.5-9b
                hf_repo=unsloth/Qwen3.5-9B-GGUF
                ;;
            *)
                echo "No llama.cpp configuration for model '$model'" >&2
                exit 1
                ;;
        esac
        uv run hf download "$hf_repo" --include "*$quant_tag.gguf"
        start_llama_server -hf "$hf_repo:$quant_tag" -np "$max_parallel" --jinja -fa on
        ;;
    vertex_ai)
        : "${VERTEXAI_PROJECT:?'project must be set'}"
        uv_args+=("--extra" "gcp")
        max_parallel=50
        LINUX_MCP_GATEKEEPER__BACKEND=vertex
        vertex_location="${VERTEXAI_LOCATION:-global}"
        vertex_openapi_base="https://aiplatform.googleapis.com/v1/projects/${VERTEXAI_PROJECT}/locations/${vertex_location}/endpoints/openapi"
        case $model in
            claude-*)
                LINUX_MCP_GATEKEEPER__PROVIDER=anthropic
                LINUX_MCP_GATEKEEPER__MODEL="$model"
                ;;
            gemini-*)
                LINUX_MCP_GATEKEEPER__PROVIDER=gemini
                LINUX_MCP_GATEKEEPER__MODEL="$model"
                ;;
            gemma-4-26b-a4b-it)
                if [[ $reasoning == "none" ]] ; then
                    LINUX_MCP_GATEKEEPER__REASONING_EFFORT=
                fi
                LINUX_MCP_GATEKEEPER__PROVIDER=openai
                LINUX_MCP_GATEKEEPER__MODEL="${model}-maas"
                LINUX_MCP_GATEKEEPER__BASE_URL="${vertex_openapi_base}"
                LINUX_MCP_GATEKEEPER__COST=0.15e-6:0.60e-6
                ;;
            gpt-oss-20b)
                LINUX_MCP_GATEKEEPER__PROVIDER=openai
                LINUX_MCP_GATEKEEPER__MODEL="${model}-maas"
                LINUX_MCP_GATEKEEPER__BASE_URL="${vertex_openapi_base}"
                LINUX_MCP_GATEKEEPER__COST="0.07e-6:0.25e-6"
                ;;
            gpt-oss-120b)
                LINUX_MCP_GATEKEEPER__PROVIDER=openai
                LINUX_MCP_GATEKEEPER__MODEL="${model}-maas"
                LINUX_MCP_GATEKEEPER__BASE_URL="${vertex_openapi_base}"
                LINUX_MCP_GATEKEEPER__COST="0.09e-6:0.36e-6"
                ;;
        esac
        ;;
    models_corp)
        : "${OPENAI_API_KEY:?'api key must be set'}"
        SSL_CERT_FILE=${SSL_CERT_FILE:-/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem}
        export SSL_CERT_FILE
        LINUX_MCP_GATEKEEPER__PROVIDER=openai
        LINUX_MCP_GATEKEEPER__BACKEND=direct
        case $model in
            granite-*)
                LINUX_MCP_GATEKEEPER__MODEL="ibm-granite/$model"
                ;;
            gpt-oss*)
                LINUX_MCP_GATEKEEPER__MODEL="openai/$model"
                ;;
        esac
        LINUX_MCP_GATEKEEPER__BASE_URL="$(get_MC_base_url "$model")"
        max_parallel=5
        ;;
    openrouter)
        : "${OPENROUTER_API_KEY:?'api key must be set'}"
        LINUX_MCP_GATEKEEPER__PROVIDER=openrouter
        LINUX_MCP_GATEKEEPER__BACKEND=direct
        if [[ -n $quantization ]] ; then
            LINUX_MCP_GATEKEEPER__QUANTIZATION=$quantization
        fi
        case $model in
            claude-*)
                LINUX_MCP_GATEKEEPER__MODEL="anthropic/$model"
                ;;
            gemma-*)
                LINUX_MCP_GATEKEEPER__MODEL="google/$model"
                ;;
            gpt-oss-*)
                LINUX_MCP_GATEKEEPER__MODEL="openai/$model"
                ;;
            gpt-*)
                LINUX_MCP_GATEKEEPER__MODEL="openai/$model"
                ;;
            granite-*)
                LINUX_MCP_GATEKEEPER__MODEL="ibm-granite/$model"
                ;;
            qwen*)
                LINUX_MCP_GATEKEEPER__MODEL="qwen/$model"
                ;;
        esac
        ;;
esac

export LINUX_MCP_GATEKEEPER__PROVIDER LINUX_MCP_GATEKEEPER__BACKEND LINUX_MCP_GATEKEEPER__MODEL
export LINUX_MCP_GATEKEEPER__COST LINUX_MCP_GATEKEEPER__REASONING_EFFORT
[[ -n "${LINUX_MCP_GATEKEEPER__QUANTIZATION:-}" ]] && export LINUX_MCP_GATEKEEPER__QUANTIZATION
[[ -n "${LINUX_MCP_GATEKEEPER__BASE_URL:-}" ]] && export LINUX_MCP_GATEKEEPER__BASE_URL
[[ -n "${LINUX_MCP_GATEKEEPER__TEMPLATE_KWARGS:-}" ]] && export LINUX_MCP_GATEKEEPER__TEMPLATE_KWARGS

variant_suffix=""
if [[ -n "$variant" ]] ; then
    variant_suffix="+${variant}"
fi

mkdir -p "${output_dir}"

run_eval_args=(--max-parallel="$max_parallel" -f json --output-all --all)
if [[ "$save" = true ]] ; then
    flags="$reasoning"
    if [[ -n "$quantization" ]] ; then
        flags="${flags},${quantization}"
    fi
    run_eval_args+=(-o "${output_dir}/$model:${flags}@${provider}${variant_suffix}.json")
fi

uv run --project="${REPO_ROOT}" "${uv_args[@]}" \
    "${SCRIPT_DIR}/run-eval.py" "${run_eval_args[@]}"
