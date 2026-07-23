"""Anthropic Messages API client for the gatekeeper."""

import os

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
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
    """Map reasoning_effort to Anthropic adaptive thinking.

    - None: omit thinking (provider default)
    - ReasoningEffort.NONE: explicitly disable thinking
    - ReasoningEffort.MINIMAL, LOW, MEDIUM, HIGH, XHIGH: adaptive thinking with effort in output_config
    """
    if reasoning_effort is None:
        return None
    if reasoning_effort == ReasoningEffort.NONE:
        return {"type": "disabled"}
    return {"type": "adaptive"}


def build_messages_body(prompt: str, *, include_model: bool, max_tokens: int) -> dict[str, Any]:
    assert CONFIG.gatekeeper is not None
    body: dict[str, Any] = {
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": CONFIG.gatekeeper.temperature,
    }
    if include_model:
        body["model"] = CONFIG.gatekeeper.model

    output_config: dict[str, Any] = {}
    if CONFIG.gatekeeper.structured_output:
        output_config = anthropic_output_config()

    reasoning_effort = CONFIG.gatekeeper.reasoning_effort
    thinking = _anthropic_thinking_block(reasoning_effort)
    if thinking is not None:
        body["thinking"] = thinking
    if reasoning_effort is not None and reasoning_effort != ReasoningEffort.NONE:
        output_config["effort"] = reasoning_effort.value

    if output_config:
        body["output_config"] = output_config
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
