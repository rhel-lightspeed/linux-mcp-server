"""Vertex AI gatekeeper client with model-based API routing."""

from typing import Literal

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.anthropic_client import complete_anthropic
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_location
from linux_mcp_server.gatekeeper.gcp_auth import get_gcp_project
from linux_mcp_server.gatekeeper.gemini_client import complete_gemini
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.openai_client import complete_openai


ANTHROPIC_VERTEX_VERSION = "vertex-2023-10-16"


def _vertex_api_style(model: str) -> Literal["anthropic", "gemini", "openai_compatible"]:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gemini"):
        return "gemini"
    return "openai_compatible"


def _get_vertex_openapi_base_url() -> str:
    assert CONFIG.gatekeeper is not None
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


async def complete_vertex_ai(
    prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> GatekeeperCompletion:
    assert CONFIG.gatekeeper is not None
    model = CONFIG.gatekeeper.model
    auth = {**_vertex_auth_headers(), "Content-Type": "application/json"}
    match _vertex_api_style(model):
        case "anthropic":
            return await complete_anthropic(
                prompt,
                max_tokens=max_tokens,
                timeout=timeout,
                url=_anthropic_vertex_url(model),
                headers=auth,
                include_model=False,
                anthropic_version=ANTHROPIC_VERTEX_VERSION,
            )
        case "gemini":
            return await complete_gemini(
                prompt,
                max_tokens=max_tokens,
                timeout=timeout,
                url=_gemini_vertex_url(model),
                headers=auth,
            )
        case "openai_compatible":
            return await complete_openai(
                prompt,
                max_tokens=max_tokens,
                timeout=timeout,
                base_url=_get_vertex_openapi_base_url(),
                headers=auth,
            )
