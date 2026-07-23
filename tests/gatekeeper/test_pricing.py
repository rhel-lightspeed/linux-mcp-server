import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import OpenAIGatekeeperConfig
from linux_mcp_server.gatekeeper import pricing


@pytest.fixture(autouse=True)
def reset_pricing_cache():
    pricing.reset_models_dev_cache()
    yield
    pricing.reset_models_dev_cache()


@pytest.fixture
def gatekeeper_config(mocker):
    config = GatekeeperConfig(provider=GatekeeperProvider.ANTHROPIC, model="claude-sonnet-4-6")
    mocker.patch.object(CONFIG, "gatekeeper", config)
    return config


class TestComputeCost:
    def test_api_usage_cost(self):
        cost, source = pricing.compute_cost(10, 5, usage_cost=0.42)
        assert cost == 0.42
        assert source == "api"

    def test_config_override(self, gatekeeper_config, mocker):
        gatekeeper_config.cost = (1e-6, 4e-6)
        cost, source = pricing.compute_cost(100, 50, usage_cost=None)
        assert cost == pytest.approx(100 * 1e-6 + 50 * 4e-6)
        assert source == "config"

    def test_models_dev_lookup(self, gatekeeper_config, mocker):
        gatekeeper_config.cost = None
        mocker.patch.object(
            pricing,
            "_load_models_dev_pricing",
            return_value={
                "anthropic": {
                    "models": {
                        "claude-sonnet-4-6": {"cost": {"input": 3.0, "output": 15.0}},
                    }
                }
            },
        )
        cost, source = pricing.compute_cost(1_000_000, 1_000_000, usage_cost=None)
        assert cost == pytest.approx(3.0 + 15.0)
        assert source == "models_dev"

    def test_unknown_model_defaults_to_zero(self, gatekeeper_config, mocker):
        gatekeeper_config.model = "unknown-model-xyz"
        gatekeeper_config.cost = None
        mocker.patch.object(pricing, "_load_models_dev_pricing", return_value={})
        cost, source = pricing.compute_cost(1_000_000, 1_000_000, usage_cost=None)
        assert cost == 0.0
        assert source == "fallback"

    def test_local_inference_is_zero(self, gatekeeper_config, mocker):
        gatekeeper_config.provider = GatekeeperProvider.OPENAI
        gatekeeper_config.model = "google/gemma-4-26b-a4b"
        gatekeeper_config.cost = None
        gatekeeper_config.openai = OpenAIGatekeeperConfig(base_url="http://localhost:8080/v1")
        mocker.patch.object(pricing, "_load_models_dev_pricing", return_value={})
        cost, source = pricing.compute_cost(1_000, 1_000, usage_cost=None)
        assert cost == 0.0
        assert source == "local"

    def test_fetch_failure_defaults_to_zero(self, gatekeeper_config, mocker):
        gatekeeper_config.cost = None
        mocker.patch("linux_mcp_server.gatekeeper.pricing.httpx.Client", side_effect=OSError("offline"))
        cost, source = pricing.compute_cost(1_000_000, 0, usage_cost=None)
        assert cost == 0.0
        assert source == "fallback"
