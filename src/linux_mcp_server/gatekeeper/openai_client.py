"""OpenAI Responses and Chat Completions clients for the gatekeeper."""

import os

from typing import Any
from urllib.parse import urlparse

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.schema import openai_response_format
from linux_mcp_server.gatekeeper.schema import openai_text_format
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


def _prefers_openai_chat_completions(base_url: str) -> bool:
    """Hosts known to expose only Chat Completions, not the Responses API."""
    path = urlparse(base_url).path or ""
    return "/endpoints/openapi" in path


def _openai_template_kwargs() -> dict[str, Any]:
    if CONFIG.gatekeeper.openai is None:
        return {}
    return CONFIG.gatekeeper.openai.template_kwargs


def _apply_chat_completions_extras(body: dict[str, Any]) -> dict[str, Any]:
    """Merge template_kwargs into Chat Completions bodies (llama.cpp, etc.)."""
    template_kwargs = _openai_template_kwargs()
    if template_kwargs:
        body["chat_template_kwargs"] = template_kwargs
    return body


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


def build_chat_completions_body(prompt: str, *, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": normalize_model_id(CONFIG.gatekeeper.model or ""),
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": max_tokens,
        "temperature": CONFIG.gatekeeper.temperature,
    }
    if CONFIG.gatekeeper.structured_output:
        body["response_format"] = openai_response_format()
    reasoning_effort = CONFIG.gatekeeper.reasoning_effort
    if reasoning_effort is not None:
        body["reasoning_effort"] = reasoning_effort.value
    return _apply_chat_completions_extras(body)


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


def extract_chat_completions_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    return (content or "").strip() if isinstance(content, str) else ""


def complete_openai(prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    base_url = _get_openai_base_url()
    headers = {
        **_openai_auth_headers(),
        "Content-Type": "application/json",
    }

    # Try the Responses API first, falling back to Chat Completions if it's not available.
    if not _prefers_openai_chat_completions(base_url):
        try:
            response = post_json(
                provider="openai",
                url=f"{base_url}/responses",
                headers=headers,
                body=_build_responses_body(prompt, max_tokens=max_tokens),
                timeout=timeout,
            )
            return GatekeeperCompletion(text=_extract_responses_text(response))
        except GatekeeperHTTPError as exc:
            if exc.status_code not in {404, 405}:
                raise

    response = post_json(
        provider="openai",
        url=f"{base_url}/chat/completions",
        headers=headers,
        body=build_chat_completions_body(prompt, max_tokens=max_tokens),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_chat_completions_text(response))
