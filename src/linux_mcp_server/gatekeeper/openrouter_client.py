"""OpenRouter Chat Completions client for the gatekeeper."""

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import get_openrouter_base_url
from linux_mcp_server.gatekeeper.http_utils import normalize_openrouter_model_id
from linux_mcp_server.gatekeeper.http_utils import openrouter_auth_headers
from linux_mcp_server.gatekeeper.http_utils import openrouter_reasoning_block
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.schema import openai_response_format


def _build_chat_completions_body(prompt: str) -> dict[str, Any]:
    provider: dict[str, Any] = {"require_parameters": True}
    if CONFIG.gatekeeper.quantization:
        provider["quantizations"] = [CONFIG.gatekeeper.quantization]

    body: dict[str, Any] = {
        "model": normalize_openrouter_model_id(CONFIG.gatekeeper.model or ""),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": CONFIG.gatekeeper.temperature,
        "provider": provider,
    }
    if CONFIG.gatekeeper.structured_output:
        body["response_format"] = openai_response_format()
    reasoning = openrouter_reasoning_block(CONFIG.gatekeeper.reasoning_effort)
    if reasoning is not None:
        body["reasoning"] = reasoning
    if CONFIG.gatekeeper.template_kwargs:
        body["chat_template_kwargs"] = CONFIG.gatekeeper.template_kwargs
    return body


def _extract_chat_completions_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    return (content or "").strip() if isinstance(content, str) else ""


def _extract_usage(response: dict[str, Any]) -> tuple[int, int, float | None]:
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        return 0, 0, None
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cost = usage.get("cost")
    return (
        int(prompt_tokens) if isinstance(prompt_tokens, int) else 0,
        int(completion_tokens) if isinstance(completion_tokens, int) else 0,
        float(cost) if isinstance(cost, (int, float)) else None,
    )


def complete_openrouter(prompt: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    base_url = get_openrouter_base_url()
    headers = {
        **openrouter_auth_headers(),
        "Content-Type": "application/json",
    }
    response = post_json(
        provider="openrouter",
        url=f"{base_url}/chat/completions",
        headers=headers,
        body=_build_chat_completions_body(prompt),
        timeout=timeout,
    )
    prompt_tokens, completion_tokens, usage_cost = _extract_usage(response)
    return GatekeeperCompletion(
        text=_extract_chat_completions_text(response),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        usage_cost=usage_cost,
    )
