"""OpenAI Responses and Chat Completions clients for the gatekeeper."""

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError
from linux_mcp_server.gatekeeper.http_utils import get_openai_base_url
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import openai_auth_headers
from linux_mcp_server.gatekeeper.http_utils import openai_reasoning_block
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.http_utils import prefers_openai_chat_completions
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.schema import openai_response_format
from linux_mcp_server.gatekeeper.schema import openai_text_format


def _apply_chat_completions_extras(body: dict[str, Any]) -> dict[str, Any]:
    """Merge template_kwargs into Chat Completions bodies (llama.cpp, etc.)."""
    if CONFIG.gatekeeper.template_kwargs:
        body["chat_template_kwargs"] = CONFIG.gatekeeper.template_kwargs
    return body


def _build_responses_body(prompt: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": normalize_model_id(CONFIG.gatekeeper.model or ""),
        "input": prompt,
        "temperature": CONFIG.gatekeeper.temperature,
        "store": False,
    }
    if CONFIG.gatekeeper.structured_output:
        body["text"] = openai_text_format()
    reasoning = openai_reasoning_block(CONFIG.gatekeeper.reasoning_effort)
    if reasoning is not None:
        body["reasoning"] = reasoning
    return body


def _build_chat_completions_body(prompt: str) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": normalize_model_id(CONFIG.gatekeeper.model or ""),
        "messages": [{"role": "user", "content": prompt}],
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


def _extract_chat_completions_text(response: dict[str, Any]) -> str:
    choices = response.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    return (content or "").strip() if isinstance(content, str) else ""


def complete_openai(prompt: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    base_url = get_openai_base_url()
    headers = {
        **openai_auth_headers(),
        "Content-Type": "application/json",
    }

    # Try the Responses API first, falling back to Chat Completions if it's not available.
    if not prefers_openai_chat_completions(base_url):
        try:
            response = post_json(
                provider="openai",
                url=f"{base_url}/responses",
                headers=headers,
                body=_build_responses_body(prompt),
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
        body=_build_chat_completions_body(prompt),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=_extract_chat_completions_text(response))
