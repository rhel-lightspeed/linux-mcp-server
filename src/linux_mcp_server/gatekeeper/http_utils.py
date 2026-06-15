"""Shared helpers for gatekeeper HTTP clients."""

from typing import Any

import requests


DEFAULT_TIMEOUT_SECONDS = 120


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


def normalize_model_id(model: str) -> str:
    for prefix in ("openai/", "anthropic/", "vertex_ai/", "gemini/"):
        if model.startswith(prefix):
            return model[len(prefix) :]
    return model
