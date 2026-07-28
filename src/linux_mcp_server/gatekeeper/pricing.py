"""Gatekeeper cost estimation from usage tokens and pricing tables."""

import logging

from functools import cache

import httpx

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import TypeAdapter

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperProvider


logger = logging.getLogger("linux-mcp-server")


MODELS_DEV_API_URL = "https://models.dev/api.json"


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float | None = None


class TokenRates(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_per_token: float
    output_per_token: float


class ModelsDevCost(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input: float
    output: float


class ModelsDevModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cost: ModelsDevCost | None = None


class ModelsDevProvider(BaseModel):
    model_config = ConfigDict(extra="ignore")

    models: dict[str, ModelsDevModel] = Field(default_factory=dict)


_ModelsDevPayload = TypeAdapter(dict[str, ModelsDevProvider])


def _rates_from_mtok(input_mtok: float, output_mtok: float) -> TokenRates:
    return TokenRates(
        input_per_token=input_mtok / 1_000_000,
        output_per_token=output_mtok / 1_000_000,
    )


def _model_lookup_candidates(model: str) -> list[str]:
    """Creates a list of variant model IDs based on the given model ID."""
    candidates = [model]
    if model.endswith("-maas"):
        candidates.append(model[: -len("-maas")])
    if "/" in model:
        candidates.append(model.split("/", 1)[1])
    seen: set[str] = set()
    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            ordered.append(candidate)
    return ordered


def _models_dev_provider_key(provider: GatekeeperProvider) -> str:
    """Maps the provider to the corresponding models.dev provider name."""
    match provider:
        case GatekeeperProvider.GEMINI:
            return "google"
        case GatekeeperProvider.VERTEX_AI:
            return "google-vertex"
        case _:
            return provider.value


@cache
def _load_models_dev_payload() -> dict[str, ModelsDevProvider]:
    """Loads pricing from the models.dev API. Returns an empty dict if unavailable."""
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(MODELS_DEV_API_URL)
            response.raise_for_status()
            pricing = _ModelsDevPayload.validate_python(response.json())
            logger.debug("Loaded gatekeeper pricing from models.dev API")
            return pricing
    except Exception as exc:
        logger.warning("Failed to fetch models.dev pricing (%s); defaulting to $0", exc)
        return {}


def _lookup_models_dev_cost(provider_key: str, model: str) -> tuple[float, float] | None:
    """Looks up the cost per million tokens for a given model and provider in the models.dev pricing."""
    pricing = _load_models_dev_payload()
    provider = pricing.get(provider_key)
    if provider is None:
        return None

    for candidate in _model_lookup_candidates(model):
        entry = provider.models.get(candidate)
        if entry is None or entry.cost is None:
            continue
        return entry.cost.input, entry.cost.output
    return None


def resolve_token_rates() -> TokenRates:
    assert CONFIG.gatekeeper is not None
    if CONFIG.gatekeeper.cost is not None:
        input_per_token, output_per_token = CONFIG.gatekeeper.cost
        return TokenRates(
            input_per_token=input_per_token,
            output_per_token=output_per_token,
        )

    provider = CONFIG.gatekeeper.provider
    model = CONFIG.gatekeeper.model
    provider_key = _models_dev_provider_key(provider)
    models_dev_cost = _lookup_models_dev_cost(provider_key, model)
    if models_dev_cost is not None:
        return _rates_from_mtok(models_dev_cost[0], models_dev_cost[1])

    return _rates_from_mtok(0.0, 0.0)


def compute_cost(
    prompt_tokens: int,
    completion_tokens: int,
    *,
    usage_cost: float | None,
) -> float:
    if usage_cost is not None:
        return usage_cost

    rates = resolve_token_rates()
    return prompt_tokens * rates.input_per_token + completion_tokens * rates.output_per_token


def reset_models_dev_cache() -> None:
    """Clear the cached models.dev pricing (for tests)."""
    _load_models_dev_payload.cache_clear()
