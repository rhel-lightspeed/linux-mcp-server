"""Provider routing for gatekeeper LLM calls."""

import logging

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.gatekeeper.anthropic_client import complete_anthropic
from linux_mcp_server.gatekeeper.gemini_client import complete_gemini
from linux_mcp_server.gatekeeper.openai_client import complete_openai
from linux_mcp_server.gatekeeper.openrouter_client import complete_openrouter
from linux_mcp_server.gatekeeper.vertex_ai_client import complete_vertex_ai
from linux_mcp_server.models import GatekeeperCompletion


logger = logging.getLogger("linux-mcp-server")


def _infer_provider_from_model(model: str) -> GatekeeperProvider:
    if model.startswith("openrouter/"):
        return GatekeeperProvider.OPENROUTER
    if model.startswith("anthropic/") or model.startswith("claude"):
        return GatekeeperProvider.ANTHROPIC
    if model.startswith("gemini"):
        return GatekeeperProvider.GEMINI
    return GatekeeperProvider.OPENAI


def resolve_provider() -> GatekeeperProvider:
    if CONFIG.gatekeeper.provider is not None:
        return CONFIG.gatekeeper.provider
    if not CONFIG.gatekeeper.model:
        raise ValueError("To use run_script tools, you must set LINUX_MCP_GATEKEEPER__MODEL")
    return _infer_provider_from_model(CONFIG.gatekeeper.model)


def complete_gatekeeper(prompt: str) -> GatekeeperCompletion:
    provider = resolve_provider()
    match provider:
        case GatekeeperProvider.OPENAI:
            completion = complete_openai(prompt)
        case GatekeeperProvider.ANTHROPIC:
            completion = complete_anthropic(prompt)
        case GatekeeperProvider.GEMINI:
            completion = complete_gemini(prompt)
        case GatekeeperProvider.OPENROUTER:
            completion = complete_openrouter(prompt)
        case GatekeeperProvider.VERTEX_AI:
            completion = complete_vertex_ai(prompt)
        case _:  # pragma: no cover
            raise ValueError(f"Unsupported gatekeeper provider: {provider}")

    logger.info(f"Gatekeeper response: {completion.text}")
    return completion
