"""Gemini generateContent client for the gatekeeper."""

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperBackend
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_access_token
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import gemini_thinking_level
from linux_mcp_server.gatekeeper.http_utils import get_google_api_key
from linux_mcp_server.gatekeeper.http_utils import GOOGLE_AI_BASE_URL
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.schema import gemini_generation_config


def _build_body(prompt: str) -> dict[str, Any]:
    generation_config = gemini_generation_config(
        temperature=CONFIG.gatekeeper.temperature,
        structured_output=CONFIG.gatekeeper.structured_output,
    )
    thinking_level = gemini_thinking_level(CONFIG.gatekeeper.reasoning_effort)
    if thinking_level is not None:
        generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }


def _vertex_url(model: str) -> str:
    project = get_gcp_project()
    location = get_gcp_location()
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent"


def _extract_text(response: dict[str, Any]) -> str:
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
    body = _build_body(prompt)

    if CONFIG.gatekeeper.backend == GatekeeperBackend.VERTEX:
        headers = {
            "Authorization": f"Bearer {get_gcp_access_token()}",
            "Content-Type": "application/json",
        }
        response = post_json(
            provider="gemini",
            url=_vertex_url(model),
            headers=headers,
            body=body,
            timeout=timeout,
        )
        return GatekeeperCompletion(text=_extract_text(response))

    api_key = get_google_api_key()
    headers = {"Content-Type": "application/json"}
    response = post_json(
        provider="gemini",
        url=f"{GOOGLE_AI_BASE_URL}/models/{model}:generateContent?key={api_key}",
        headers=headers,
        body=body,
        timeout=timeout,
    )
    return GatekeeperCompletion(text=_extract_text(response))
