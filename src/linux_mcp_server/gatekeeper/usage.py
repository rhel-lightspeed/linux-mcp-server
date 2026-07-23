"""Token and cost extraction from gatekeeper LLM API responses."""

from typing import Any

from linux_mcp_server.gatekeeper.pricing import Usage


def extract_openai_chat_completions_usage(response: dict[str, Any]) -> Usage:
    """Extract prompt and completion tokens from OpenAI chat completions response."""
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        return Usage()
    return Usage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
    )


def extract_openai_responses_usage(response: dict[str, Any]) -> Usage:
    """Extract input and output tokens from OpenAI responses response."""
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        return Usage()
    return Usage(
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
    )


def extract_anthropic_usage(response: dict[str, Any]) -> Usage:
    """Extract input and output tokens from Anthropic response."""
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        return Usage()
    return Usage(
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
    )


def extract_gemini_usage(response: dict[str, Any]) -> Usage:
    """Extract prompt and candidate tokens from Gemini response."""
    usage = response.get("usageMetadata", {})
    if not isinstance(usage, dict):
        return Usage()
    return Usage(
        input_tokens=int(usage.get("promptTokenCount") or 0),
        output_tokens=int(usage.get("candidatesTokenCount") or 0),
    )


def extract_openrouter_usage(response: dict[str, Any]) -> Usage:
    """Extract prompt and completion tokens from OpenRouter response, and cost if available."""
    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        return Usage()
    cost_raw = usage.get("cost")
    cost = float(cost_raw) if isinstance(cost_raw, (int, float)) else None
    return Usage(
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
        cost=cost,
    )
