"""Vertex AI gatekeeper client with model-based API routing."""

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.anthropic_client import build_messages_body
from linux_mcp_server.gatekeeper.anthropic_client import extract_messages_text
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project
from linux_mcp_server.gatekeeper.gemini_client import build_gemini_body
from linux_mcp_server.gatekeeper.gemini_client import extract_gemini_text
from linux_mcp_server.gatekeeper.http_utils import ANTHROPIC_VERTEX_VERSION
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import get_vertex_openapi_base_url
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.http_utils import vertex_api_style
from linux_mcp_server.gatekeeper.http_utils import vertex_auth_headers
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.openai_client import build_chat_completions_body
from linux_mcp_server.gatekeeper.openai_client import extract_chat_completions_text


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


def _complete_anthropic_on_vertex(prompt: str, *, timeout: int) -> GatekeeperCompletion:
    model = normalize_model_id(CONFIG.gatekeeper.model or "")
    body = build_messages_body(prompt, include_model=False)
    body["anthropic_version"] = ANTHROPIC_VERTEX_VERSION
    response = post_json(
        provider="anthropic",
        url=_anthropic_vertex_url(model),
        headers={**vertex_auth_headers(), "Content-Type": "application/json"},
        body=body,
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_messages_text(response))


def _complete_gemini_on_vertex(prompt: str, *, timeout: int) -> GatekeeperCompletion:
    model = normalize_model_id(CONFIG.gatekeeper.model or "")
    response = post_json(
        provider="gemini",
        url=_gemini_vertex_url(model),
        headers={**vertex_auth_headers(), "Content-Type": "application/json"},
        body=build_gemini_body(prompt),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_gemini_text(response))


def _complete_openai_compatible_on_vertex(prompt: str, *, timeout: int) -> GatekeeperCompletion:
    base_url = get_vertex_openapi_base_url()
    response = post_json(
        provider="openai",
        url=f"{base_url}/chat/completions",
        headers={**vertex_auth_headers(), "Content-Type": "application/json"},
        body=build_chat_completions_body(prompt),
        timeout=timeout,
    )
    return GatekeeperCompletion(text=extract_chat_completions_text(response))


def complete_vertex_ai(prompt: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> GatekeeperCompletion:
    model = CONFIG.gatekeeper.model or ""
    match vertex_api_style(model):
        case "anthropic":
            return _complete_anthropic_on_vertex(prompt, timeout=timeout)
        case "gemini":
            return _complete_gemini_on_vertex(prompt, timeout=timeout)
        case "openai_compatible":
            return _complete_openai_compatible_on_vertex(prompt, timeout=timeout)
        case _:  # pragma: no cover
            raise ValueError(f"Unsupported Vertex AI API style for model: {model}")
