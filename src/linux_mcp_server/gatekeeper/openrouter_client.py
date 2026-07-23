"""OpenRouter Chat Completions client for the gatekeeper."""

import os

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.schema import openai_response_format
from linux_mcp_server.gatekeeper.usage import extract_openrouter_usage
from linux_mcp_server.models import GatekeeperCompletion


OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def _get_openrouter_base_url() -> str:
    assert CONFIG.gatekeeper is not None
    configured = CONFIG.gatekeeper.openrouter.base_url if CONFIG.gatekeeper.openrouter else None
    return (configured or OPENROUTER_DEFAULT_BASE_URL).rstrip("/")


def _get_openrouter_api_key() -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter gatekeeper provider.")
    return api_key


def _openrouter_auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_openrouter_api_key()}"}


def _openrouter_reasoning_block(reasoning_effort: ReasoningEffort | None) -> dict[str, Any] | None:
    if reasoning_effort is None:
        return None
    if reasoning_effort == ReasoningEffort.NONE:
        return {"enabled": False}
    return {"enabled": True, "effort": reasoning_effort.value}


def _openrouter_config() -> dict[str, Any]:
    assert CONFIG.gatekeeper is not None
    if CONFIG.gatekeeper.openrouter is None:
        return {"quantization": None, "template_kwargs": {}}
    return {
        "quantization": CONFIG.gatekeeper.openrouter.quantization,
        "template_kwargs": CONFIG.gatekeeper.openrouter.template_kwargs,
    }


def _build_chat_completions_body(prompt: str, *, max_tokens: int) -> dict[str, Any]:
    assert CONFIG.gatekeeper is not None
    openrouter = _openrouter_config()
    provider: dict[str, Any] = {"require_parameters": True}
    if openrouter["quantization"]:
        provider["quantizations"] = [openrouter["quantization"]]

    body: dict[str, Any] = {
        "model": CONFIG.gatekeeper.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": CONFIG.gatekeeper.temperature,
        "provider": provider,
    }
    if CONFIG.gatekeeper.structured_output:
        body["response_format"] = openai_response_format()
    reasoning = _openrouter_reasoning_block(CONFIG.gatekeeper.reasoning_effort)
    if reasoning is not None:
        body["reasoning"] = reasoning
    if openrouter["template_kwargs"]:
        body["chat_template_kwargs"] = openrouter["template_kwargs"]
    return body


def _extract_chat_completions_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    return (content or "").strip() if isinstance(content, str) else ""


async def complete_openrouter(
    prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> GatekeeperCompletion:
    base_url = _get_openrouter_base_url()
    headers = {
        **_openrouter_auth_headers(),
        "Content-Type": "application/json",
    }
    response = await post_json(
        provider="openrouter",
        url=f"{base_url}/chat/completions",
        headers=headers,
        body=_build_chat_completions_body(prompt, max_tokens=max_tokens),
        timeout=timeout,
    )
    usage = extract_openrouter_usage(response)
    return GatekeeperCompletion(
        text=_extract_chat_completions_text(response),
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
        usage_cost=usage.cost,
    )
