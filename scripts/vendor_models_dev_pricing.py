#!/usr/bin/env python3
"""Refresh the vendored models.dev pricing snapshot used by the gatekeeper."""

import json
import sys
import urllib.request

from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "src/linux_mcp_server/gatekeeper/data/models_dev_fallback.json"
MODELS_DEV_URL = "https://models.dev/api.json"

# Provider -> model IDs used by eval/gatekeeper/standard-evals.sh
WANTED: dict[str, list[str]] = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
    "openai": ["gpt-5.4", "gpt-oss-20b", "gpt-oss-120b"],
    "google": ["gemini-2.0-flash", "gemini-3.1-pro-preview"],
    "openrouter": [
        "openai/gpt-oss-120b",
        "anthropic/claude-sonnet-4-6",
        "google/gemma-4-26b-a4b-it",
        "ibm-granite/granite-4.0-h-small",
        "qwen/qwen3.5-35b-a3b",
    ],
}


@dataclass(frozen=True)
class TokenCostPerMillion:
    """USD per million tokens, matching models.dev's cost.input / cost.output fields."""

    input: float
    output: float

    def to_dict(self) -> dict[str, float]:
        return {"input": self.input, "output": self.output}


@dataclass(frozen=True)
class ModelPricing:
    """Pricing structure for a single model. Contains the cost per million tokens."""

    cost: TokenCostPerMillion

    def to_dict(self) -> dict[str, Any]:
        return {"cost": self.cost.to_dict()}

    @classmethod
    def from_models_dev_entry(cls, entry: object) -> "ModelPricing | None":
        if not isinstance(entry, dict):
            return None
        cost = entry.get("cost")
        if not isinstance(cost, dict):
            return None
        input_mtok = cost.get("input")
        output_mtok = cost.get("output")
        if not isinstance(input_mtok, (int, float)) or not isinstance(output_mtok, (int, float)):
            return None
        return cls(cost=TokenCostPerMillion(input=float(input_mtok), output=float(output_mtok)))


@dataclass
class ProviderPricing:
    """Pricing structure for a single provider. Maps model ID to its pricing."""

    models: dict[str, ModelPricing]

    def to_dict(self) -> dict[str, Any]:
        return {"models": {model_id: pricing.to_dict() for model_id, pricing in self.models.items()}}


@dataclass
class PricingSnapshot:
    """Snapshot of models.dev pricing for the gatekeeper. Maps provider name to a pricing structure."""

    providers: dict[str, ProviderPricing]

    def to_dict(self) -> dict[str, Any]:
        return {provider: pricing.to_dict() for provider, pricing in self.providers.items()}


def _models_dev_catalog(data: dict[str, Any], provider: str) -> dict[str, Any]:
    """Extract the models catalog for a given provider from the models.dev data."""
    provider_data = data.get(provider, {})
    if not isinstance(provider_data, dict):
        return {}
    models = provider_data.get("models", {})
    return models if isinstance(models, dict) else {}


def build_snapshot(data: dict[str, Any]) -> tuple[PricingSnapshot, list[str]]:
    """Build a pricing snapshot from the models.dev data."""
    providers: dict[str, ProviderPricing] = {}
    missing: list[str] = []

    for provider, model_ids in WANTED.items():
        src_models = _models_dev_catalog(data, provider)
        picked: dict[str, ModelPricing] = {}
        for model_id in model_ids:
            pricing = ModelPricing.from_models_dev_entry(src_models.get(model_id))
            if pricing is None:
                missing.append(f"{provider}/{model_id}")
            else:
                picked[model_id] = pricing
        if picked:
            providers[provider] = ProviderPricing(models=picked)

    return PricingSnapshot(providers=providers), missing


def main() -> int:
    with urllib.request.urlopen(MODELS_DEV_URL, timeout=30) as response:
        data = json.load(response)

    snapshot, missing = build_snapshot(data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(snapshot.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")

    if missing:
        print("Missing pricing for:", ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
