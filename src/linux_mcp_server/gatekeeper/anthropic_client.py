"""Anthropic Messages API client for the gatekeeper."""

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperBackend
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_access_token
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project
from linux_mcp_server.gatekeeper.http_utils import ANTHROPIC_API_URL
from linux_mcp_server.gatekeeper.http_utils import ANTHROPIC_API_VERSION
from linux_mcp_server.gatekeeper.http_utils import ANTHROPIC_DEFAULT_MAX_TOKENS
from linux_mcp_server.gatekeeper.http_utils import anthropic_thinking_block
from linux_mcp_server.gatekeeper.http_utils import ANTHROPIC_VERTEX_VERSION
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import get_anthropic_api_key
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.schema import anthropic_output_config


def _build_messages_body(prompt: str, *, include_model: bool) -> dict[str, Any]:
    body: dict[str, Any] = {
        "max_tokens": ANTHROPIC_DEFAULT_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": CONFIG.gatekeeper.temperature,
    }
    if include_model:
        body["model"] = normalize_model_id(CONFIG.gatekeeper.model or "")
    if CONFIG.gatekeeper.structured_output:
        body["output_config"] = anthropic_output_config()
    thinking = anthropic_thinking_block(CONFIG.gatekeeper.reasoning_effort)
    if thinking is not None:
        body["thinking"] = thinking
    return body


def _vertex_url(model: str) -> str:
    project = get_gcp_project()
    location = get_gcp_location()
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project}/locations/{location}/publishers/anthropic/models/{model}:rawPredict"


def _extract_messages_text(response: dict[str, Any]) -> str:
    for item in response.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                return text.strip()
    return ""


def complete_anthropic(prompt: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    model = normalize_model_id(CONFIG.gatekeeper.model or "")

    if CONFIG.gatekeeper.backend == GatekeeperBackend.VERTEX:
        body = _build_messages_body(prompt, include_model=False)
        body["anthropic_version"] = ANTHROPIC_VERTEX_VERSION
        headers = {
            "Authorization": f"Bearer {get_gcp_access_token()}",
            "Content-Type": "application/json",
        }
        response = post_json(
            provider="anthropic",
            url=_vertex_url(model),
            headers=headers,
            body=body,
            timeout=timeout,
        )
        return GatekeeperCompletion(text=_extract_messages_text(response))

    headers = {
        "x-api-key": get_anthropic_api_key(),
        "anthropic-version": ANTHROPIC_API_VERSION,
        "Content-Type": "application/json",
    }
    response = post_json(
        provider="anthropic",
        url=ANTHROPIC_API_URL,
        headers=headers,
        body=_build_messages_body(prompt, include_model=True),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=_extract_messages_text(response))
