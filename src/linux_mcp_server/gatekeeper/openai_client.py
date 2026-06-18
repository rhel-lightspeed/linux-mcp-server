"""OpenAI Responses API client for the gatekeeper."""

import os

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.schema import openai_text_format
from linux_mcp_server.gatekeeper.usage import extract_openai_responses_usage
from linux_mcp_server.models import GatekeeperCompletion


OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _openai_reasoning_block(reasoning_effort: ReasoningEffort | None) -> dict[str, Any] | None:
    if reasoning_effort is None or reasoning_effort == ReasoningEffort.DEFAULT:
        return None
    return {"effort": reasoning_effort.value}


def _get_openai_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI gatekeeper provider.")
    return api_key


def _openai_auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_openai_api_key()}"}


def _get_openai_base_url() -> str:
    configured = CONFIG.gatekeeper.openai.base_url if CONFIG.gatekeeper.openai else None
    return (configured or os.environ.get("OPENAI_API_BASE") or OPENAI_DEFAULT_BASE_URL).rstrip("/")


def _build_responses_body(prompt: str, *, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": normalize_model_id(CONFIG.gatekeeper.model or ""),
        "input": prompt,
        "max_output_tokens": max_tokens,
        "temperature": CONFIG.gatekeeper.temperature,
        "store": False,
    }
    if CONFIG.gatekeeper.structured_output:
        body["text"] = openai_text_format()
    reasoning = _openai_reasoning_block(CONFIG.gatekeeper.reasoning_effort)
    if reasoning is not None:
        body["reasoning"] = reasoning
    return body


def _extract_responses_text(response: dict[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
    return "".join(chunks).strip()


async def complete_openai(
    prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> GatekeeperCompletion:
    base_url = _get_openai_base_url()
    headers = {
        **_openai_auth_headers(),
        "Content-Type": "application/json",
    }
    response = await post_json(
        provider="openai",
        url=f"{base_url}/responses",
        headers=headers,
        body=_build_responses_body(prompt, max_tokens=max_tokens),
        timeout=timeout,
    )
    usage = extract_openai_responses_usage(response)
    return GatekeeperCompletion(
        text=_extract_responses_text(response),
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
    )
