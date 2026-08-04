import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.gatekeeper import pricing
from linux_mcp_server.gatekeeper.pricing import ModelsDevModel
from linux_mcp_server.gatekeeper.pricing import ModelsDevProvider


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
        assert pricing.compute_cost(10, 5, usage_cost=0.42) == 0.42

    def test_config_override(self, gatekeeper_config, mocker):
        gatekeeper_config.cost = (1e-6, 4e-6)
        cost = pricing.compute_cost(100, 50, usage_cost=None)
        assert cost == pytest.approx(100 * 1e-6 + 50 * 4e-6)

    @pytest.mark.parametrize(
        "provider,provider_key,model",
        [
            (GatekeeperProvider.ANTHROPIC, "anthropic", "claude-sonnet-4-6"),
            (GatekeeperProvider.ANTHROPIC, "anthropic", "claude-sonnet-4-6-maas"),  # strips -maas suffix
            (GatekeeperProvider.ANTHROPIC, "anthropic", "anthropic/claude-sonnet-4-6"),  # strips provider prefix
            (GatekeeperProvider.GEMINI, "google", "gemini-2.5-pro"),
            (GatekeeperProvider.VERTEX_AI, "google-vertex", "gemini-2.5-pro"),
        ],
    )
    def test_models_dev_lookup(self, gatekeeper_config, mocker, provider, provider_key, model):
        gatekeeper_config.provider = provider
        gatekeeper_config.model = model
        gatekeeper_config.cost = None
        catalog_model = model.split("/", 1)[-1].removesuffix("-maas")
        response = mocker.Mock()
        response.json.return_value = {
            provider_key: {
                "models": {
                    catalog_model: {"cost": {"input": 3.0, "output": 15.0}},
                }
            }
        }
        mock_client = mocker.MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = response
        mocker.patch("linux_mcp_server.gatekeeper.pricing.httpx.Client", return_value=mock_client)

        cost = pricing.compute_cost(1_000_000, 1_000_000, usage_cost=None)
        assert cost == pytest.approx(3.0 + 15.0)
        mock_client.get.assert_called_once_with(pricing.MODELS_DEV_API_URL)

    @pytest.mark.parametrize(
        "model",
        [
            "unknown-model-xyz",  # missing from provider catalog
            "model-without-cost",  # present but cost is null
            "provider/",  # empty candidate after provider prefix is skipped
        ],
    )
    def test_unknown_model_defaults_to_zero(self, gatekeeper_config, mocker, model):
        gatekeeper_config.model = model
        gatekeeper_config.cost = None
        mocker.patch.object(
            pricing,
            "_load_models_dev_payload",
            return_value={
                "anthropic": ModelsDevProvider(
                    models={
                        "model-without-cost": ModelsDevModel(cost=None),
                    }
                )
            },
        )
        assert pricing.compute_cost(1_000_000, 1_000_000, usage_cost=None) == 0.0

    def test_fetch_failure_defaults_to_zero(self, gatekeeper_config, mocker):
        gatekeeper_config.cost = None
        mocker.patch("linux_mcp_server.gatekeeper.pricing.httpx.Client", side_effect=OSError("offline"))
        assert pricing.compute_cost(1_000_000, 0, usage_cost=None) == 0.0
