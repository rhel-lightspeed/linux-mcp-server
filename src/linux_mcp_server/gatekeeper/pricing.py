"""Gatekeeper cost estimation from usage tokens and pricing tables."""

import logging
import os

from functools import cache
from typing import Any
from urllib.parse import urlparse

import httpx

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.llm import resolve_provider
from linux_mcp_server.models import CostSource
from linux_mcp_server.models import TokenRates


logger = logging.getLogger("linux-mcp-server")


MODELS_DEV_API_URL = "https://models.dev/api.json"

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _rates_from_mtok(input_mtok: float, output_mtok: float, source: CostSource) -> TokenRates:
    return TokenRates(
        input_per_token=input_mtok / 1_000_000,
        output_per_token=output_mtok / 1_000_000,
        source=source,
    )


def _model_lookup_candidates(model: str) -> list[str]:
    """Creates a list of variant model IDs based on the given model ID."""
    normalized = normalize_model_id(model)
    candidates = [normalized, model]
    if normalized.endswith("-maas"):
        candidates.append(normalized[: -len("-maas")])
    if "/" in normalized:
        candidates.append(normalized.split("/", 1)[1])
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _models_dev_provider_key(provider: GatekeeperProvider, model: str) -> str:
    """Maps the provider to the corresponding models.dev provider name."""
    match provider:
        case GatekeeperProvider.GEMINI:
            return "google"
        case GatekeeperProvider.VERTEX_AI:
            normalized = normalize_model_id(model)
            if normalized.startswith("claude"):
                return "anthropic"
            if normalized.startswith("gemini"):
                return "google"
            return "openai"
        case _:
            return provider.value


@cache
def _load_models_dev_pricing() -> dict[str, Any]:
    """Loads pricing from the models.dev API. Returns an empty dict if unavailable."""
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(MODELS_DEV_API_URL)
            response.raise_for_status()
            pricing = response.json()
            logger.debug("Loaded gatekeeper pricing from models.dev API")
            return pricing
    except Exception as exc:
        logger.debug("Failed to fetch models.dev pricing (%s); defaulting to $0", exc)
        return {}


def _lookup_models_dev_cost(provider_key: str, model: str) -> tuple[float, float] | None:
    """Looks up the cost per million tokens for a given model and provider in the models.dev pricing."""
    pricing = _load_models_dev_pricing()
    provider_data = pricing.get(provider_key, {})
    if not isinstance(provider_data, dict):
        return None
    models = provider_data.get("models", {})
    if not isinstance(models, dict):
        return None

    for candidate in _model_lookup_candidates(model):
        entry = models.get(candidate)
        if not isinstance(entry, dict):
            continue
        cost = entry.get("cost")
        if not isinstance(cost, dict):
            continue
        input_mtok = cost.get("input")
        output_mtok = cost.get("output")
        if isinstance(input_mtok, (int, float)) and isinstance(output_mtok, (int, float)):
            return float(input_mtok), float(output_mtok)
    return None


def is_local_inference() -> bool:
    provider = resolve_provider()
    if provider != GatekeeperProvider.OPENAI:
        return False
    base_url = None
    if CONFIG.gatekeeper.openai and CONFIG.gatekeeper.openai.base_url:
        base_url = CONFIG.gatekeeper.openai.base_url
    else:
        base_url = os.environ.get("OPENAI_API_BASE")
    if not base_url:
        return False
    host = (urlparse(base_url).hostname or "").lower()
    return host in _LOCAL_HOSTS


def resolve_token_rates() -> TokenRates:
    if CONFIG.gatekeeper.cost is not None:
        input_per_token, output_per_token = CONFIG.gatekeeper.cost
        return TokenRates(
            input_per_token=input_per_token,
            output_per_token=output_per_token,
            source="config",
        )

    provider = resolve_provider()
    model = CONFIG.gatekeeper.model or ""
    provider_key = _models_dev_provider_key(provider, model)
    models_dev_cost = _lookup_models_dev_cost(provider_key, model)
    if models_dev_cost is not None:
        return _rates_from_mtok(models_dev_cost[0], models_dev_cost[1], "models_dev")

    if is_local_inference():
        return _rates_from_mtok(0.0, 0.0, "local")

    return _rates_from_mtok(0.0, 0.0, "fallback")


def compute_cost(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    usage_cost: float | None,
) -> tuple[float, CostSource]:
    if usage_cost is not None:
        return usage_cost, "api"

    rates = resolve_token_rates()
    cost = prompt_tokens * rates.input_per_token + completion_tokens * rates.output_per_token
    return cost, rates.source


def reset_models_dev_cache() -> None:
    """Clear the cached models.dev pricing (for tests)."""
    _load_models_dev_pricing.cache_clear()
