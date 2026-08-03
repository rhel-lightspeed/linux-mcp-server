"""Shared helpers for gatekeeper HTTP clients."""

import os

from typing import Any
from urllib.parse import urlparse

import requests

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperBackend
from linux_mcp_server.config import ReasoningEffort


DEFAULT_TIMEOUT_SECONDS = 120

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
ANTHROPIC_VERTEX_VERSION = "vertex-2023-10-16"
ANTHROPIC_DEFAULT_MAX_TOKENS = 4096

GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GatekeeperHTTPError(RuntimeError):
    """Raised when an LLM provider returns an error response."""

    def __init__(self, provider: str, status_code: int, body: str):
        snippet = body[:500] + ("..." if len(body) > 500 else "")
        super().__init__(f"{provider} API error ({status_code}): {snippet}")
        self.provider = provider
        self.status_code = status_code
        self.body = body


def post_json(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    response = requests.post(url, headers=headers, json=body, timeout=timeout)
    if not response.ok:
        raise GatekeeperHTTPError(provider, response.status_code, response.text)
    return response.json()


def get_openai_base_url() -> str:
    return (CONFIG.gatekeeper.base_url or os.environ.get("OPENAI_API_BASE") or OPENAI_DEFAULT_BASE_URL).rstrip("/")


def prefers_openai_chat_completions(base_url: str) -> bool:
    """Hosts known to expose only Chat Completions, not the Responses API."""
    path = urlparse(base_url).path or ""
    return "/endpoints/openapi" in path


def normalize_model_id(model: str) -> str:
    for prefix in ("openai/", "anthropic/", "vertex_ai/", "gemini/"):
        if model.startswith(prefix):
            return model[len(prefix) :]
    return model


def normalize_openrouter_model_id(model: str) -> str:
    if model.startswith("openrouter/"):
        return model[len("openrouter/") :]
    return model


def get_openrouter_base_url() -> str:
    return (CONFIG.gatekeeper.base_url or OPENROUTER_DEFAULT_BASE_URL).rstrip("/")


def openai_reasoning_block(reasoning_effort: ReasoningEffort | None) -> dict[str, Any] | None:
    if reasoning_effort is None or reasoning_effort == ReasoningEffort.DEFAULT:
        return None
    return {"effort": reasoning_effort.value}


def openrouter_reasoning_block(reasoning_effort: ReasoningEffort | None) -> dict[str, Any] | None:
    if reasoning_effort is None or reasoning_effort == ReasoningEffort.DEFAULT:
        return None
    if reasoning_effort == ReasoningEffort.NONE:
        return {"enabled": False}
    return {"enabled": True, "effort": reasoning_effort.value}


def anthropic_thinking_block(reasoning_effort: ReasoningEffort | None) -> dict[str, Any] | None:
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


def gemini_thinking_level(reasoning_effort: ReasoningEffort | None) -> str | None:
    if reasoning_effort is None or reasoning_effort in {ReasoningEffort.NONE, ReasoningEffort.DEFAULT}:
        return None
    mapping = {
        ReasoningEffort.MINIMAL: "MINIMAL",
        ReasoningEffort.LOW: "LOW",
        ReasoningEffort.MEDIUM: "MEDIUM",
        ReasoningEffort.HIGH: "HIGH",
        ReasoningEffort.XHIGH: "HIGH",
    }
    return mapping.get(reasoning_effort)


def get_openai_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI gatekeeper provider.")
    return api_key


def get_openrouter_api_key() -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter gatekeeper provider.")
    return api_key


def openrouter_auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_openrouter_api_key()}"}


def get_anthropic_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for Anthropic gatekeeper provider.")
    return api_key


def get_google_api_key() -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY is required for Gemini direct backend.")
    return api_key


def openai_auth_headers() -> dict[str, str]:
    if CONFIG.gatekeeper.backend == GatekeeperBackend.VERTEX:
        from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_access_token

        return {"Authorization": f"Bearer {get_gcp_access_token()}"}
    return {"Authorization": f"Bearer {get_openai_api_key()}"}
