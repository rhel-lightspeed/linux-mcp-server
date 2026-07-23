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


async def complete_gatekeeper(prompt: str, *, max_tokens: int) -> GatekeeperCompletion:
    assert CONFIG.gatekeeper is not None
    provider = CONFIG.gatekeeper.provider
    match CONFIG.gatekeeper.provider:
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
