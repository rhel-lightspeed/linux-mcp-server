"""Gemini generateContent client for the gatekeeper."""

import os

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.schema import gemini_generation_config
from linux_mcp_server.models import GatekeeperCompletion


GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _get_google_api_key() -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY is required for Gemini direct backend.")
    return api_key


def _gemini_thinking_level(reasoning_effort: ReasoningEffort | None) -> str | None:
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


def build_gemini_body(prompt: str) -> dict[str, Any]:
    generation_config = gemini_generation_config(
        temperature=CONFIG.gatekeeper.temperature,
        structured_output=CONFIG.gatekeeper.structured_output,
    )
    thinking_level = _gemini_thinking_level(CONFIG.gatekeeper.reasoning_effort)
    if thinking_level is not None:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }


def extract_gemini_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        return ""
    content = candidates[0].get("content", {})
    parts = content.get("parts", [])
    if not parts:
        return ""
    text = parts[0].get("text")
    return text.strip() if isinstance(text, str) else ""


def complete_gemini(prompt: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    model = normalize_model_id(CONFIG.gatekeeper.model or "")
    api_key = _get_google_api_key()
    response = post_json(
        provider="gemini",
        url=f"{GOOGLE_AI_BASE_URL}/models/{model}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        body=build_gemini_body(prompt),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_gemini_text(response))
