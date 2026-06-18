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


async def complete_gatekeeper(prompt: str, *, max_tokens: int) -> GatekeeperCompletion:
    provider = resolve_provider()
    match provider:
        case GatekeeperProvider.OPENAI:
            completion = await complete_openai(prompt, max_tokens=max_tokens)
        case GatekeeperProvider.ANTHROPIC:
            completion = await complete_anthropic(prompt, max_tokens=max_tokens)
        case GatekeeperProvider.GEMINI:
            completion = await complete_gemini(prompt, max_tokens=max_tokens)
        case GatekeeperProvider.OPENROUTER:
            completion = await complete_openrouter(prompt, max_tokens=max_tokens)
        case GatekeeperProvider.VERTEX_AI:
            completion = await complete_vertex_ai(prompt, max_tokens=max_tokens)
        case _:  # pragma: no cover
            raise ValueError(f"Unsupported gatekeeper provider: {provider}")

    logger.info(f"Gatekeeper response: {completion.text}")
    return completion
