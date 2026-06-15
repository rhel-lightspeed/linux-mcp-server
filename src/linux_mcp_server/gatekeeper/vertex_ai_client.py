"""Vertex AI gatekeeper client with model-based API routing."""

from typing import Literal

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.anthropic_client import build_messages_body
from linux_mcp_server.gatekeeper.anthropic_client import extract_messages_text
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project
from linux_mcp_server.gatekeeper.gemini_client import build_gemini_body
from linux_mcp_server.gatekeeper.gemini_client import extract_gemini_text
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.openai_client import build_chat_completions_body
from linux_mcp_server.gatekeeper.openai_client import extract_chat_completions_text
from linux_mcp_server.models import GatekeeperCompletion


ANTHROPIC_VERTEX_VERSION = "vertex-2023-10-16"


def _vertex_api_style(model: str) -> Literal["anthropic", "gemini", "openai_compatible"]:
    normalized = normalize_model_id(model)
    if normalized.startswith("claude"):
        return "anthropic"
    if normalized.startswith("gemini"):
        return "gemini"
    return "openai_compatible"


def _get_vertex_openapi_base_url() -> str:
    cfg = CONFIG.gatekeeper.vertex_ai
    if cfg and cfg.base_url:
        return cfg.base_url.rstrip("/")
    from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
    from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project

    project = get_gcp_project()
    location = get_gcp_location()
    return f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}/endpoints/openapi"


def _vertex_auth_headers() -> dict[str, str]:
    from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_access_token

    return {"Authorization": f"Bearer {get_gcp_access_token()}"}


def _anthropic_vertex_url(model: str) -> str:
    project = get_gcp_project()
    location = get_gcp_location()
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project}/locations/{location}/publishers/anthropic/models/{model}:rawPredict"


def _gemini_vertex_url(model: str) -> str:
    project = get_gcp_project()
    location = get_gcp_location()
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent"


def _complete_anthropic_on_vertex(prompt: str, *, max_tokens: int, timeout: int) -> GatekeeperCompletion:
    model = normalize_model_id(CONFIG.gatekeeper.model or "")
    body = build_messages_body(prompt, include_model=False, max_tokens=max_tokens)
    body["anthropic_version"] = ANTHROPIC_VERTEX_VERSION
    response = post_json(
        provider="anthropic",
        url=_anthropic_vertex_url(model),
        headers={**_vertex_auth_headers(), "Content-Type": "application/json"},
        body=body,
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_messages_text(response))


def _complete_gemini_on_vertex(prompt: str, *, max_tokens: int, timeout: int) -> GatekeeperCompletion:
    model = normalize_model_id(CONFIG.gatekeeper.model or "")
    response = post_json(
        provider="gemini",
        url=_gemini_vertex_url(model),
        headers={**_vertex_auth_headers(), "Content-Type": "application/json"},
        body=build_gemini_body(prompt, max_tokens=max_tokens),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_gemini_text(response))


def _complete_openai_compatible_on_vertex(prompt: str, *, max_tokens: int, timeout: int) -> GatekeeperCompletion:
    base_url = _get_vertex_openapi_base_url()
    response = post_json(
        provider="openai",
        url=f"{base_url}/chat/completions",
        headers={**_vertex_auth_headers(), "Content-Type": "application/json"},
        body=build_chat_completions_body(prompt, max_tokens=max_tokens),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_chat_completions_text(response))


def complete_vertex_ai(prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    model = CONFIG.gatekeeper.model or ""
    match _vertex_api_style(model):
        case "anthropic":
            return _complete_anthropic_on_vertex(prompt, max_tokens=max_tokens, timeout=timeout)
        case "gemini":
            return _complete_gemini_on_vertex(prompt, max_tokens=max_tokens, timeout=timeout)
        case "openai_compatible":
            return _complete_openai_compatible_on_vertex(prompt, max_tokens=max_tokens, timeout=timeout)
