"""Anthropic Messages API client for the gatekeeper."""

import os

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.schema import anthropic_output_config
from linux_mcp_server.gatekeeper.usage import extract_anthropic_usage
from linux_mcp_server.models import GatekeeperCompletion


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


def _get_anthropic_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for Anthropic gatekeeper provider.")
    return api_key


def _anthropic_thinking_block(reasoning_effort: ReasoningEffort | None) -> dict[str, Any] | None:
    if reasoning_effort is None or reasoning_effort in {ReasoningEffort.NONE, ReasoningEffort.DEFAULT}:
        return None
    budget_by_effort = {
        ReasoningEffort.MINIMAL: 1024,
        ReasoningEffort.LOW: 4096,
        ReasoningEffort.MEDIUM: 8192,
        ReasoningEffort.HIGH: 16384,
        ReasoningEffort.XHIGH: 32768,
    }
    budget = budget_by_effort.get(reasoning_effort)
    if budget is None:
        return None
    return {"type": "enabled", "budget_tokens": budget}


def build_messages_body(prompt: str, *, include_model: bool, max_tokens: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": CONFIG.gatekeeper.temperature,
    }
    if include_model:
        body["model"] = normalize_model_id(CONFIG.gatekeeper.model or "")
    if CONFIG.gatekeeper.structured_output:
        body["output_config"] = anthropic_output_config()
    thinking = _anthropic_thinking_block(CONFIG.gatekeeper.reasoning_effort)
    if thinking is not None:
        body["thinking"] = thinking
    return body


def extract_messages_text(response: dict[str, Any]) -> str:
    for item in response.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                return text.strip()
    return ""


async def complete_anthropic(
    prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> GatekeeperCompletion:
    headers = {
        "x-api-key": _get_anthropic_api_key(),
        "anthropic-version": ANTHROPIC_API_VERSION,
        "Content-Type": "application/json",
    }
    response = await post_json(
        provider="anthropic",
        url=ANTHROPIC_API_URL,
        headers=headers,
        body=build_messages_body(prompt, include_model=True, max_tokens=max_tokens),
        timeout=timeout,
    )
    usage = extract_anthropic_usage(response)
    return GatekeeperCompletion(
        text=extract_messages_text(response),
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
    )
