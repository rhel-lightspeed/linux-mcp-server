import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperBackend
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.gatekeeper import anthropic_client


class TestAnthropicClient:
    @pytest.fixture
    def gatekeeper_config(self, mocker):
        mocker.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False)
        config = GatekeeperConfig(
            provider=GatekeeperProvider.ANTHROPIC,
            model="claude-sonnet-4-6",
            structured_output=True,
            temperature=0.0,
        )
        mocker.patch.object(CONFIG, "gatekeeper", config)
        return config

    def test_complete_anthropic_direct(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            return_value={"content": [{"type": "text", "text": '{"status": "OK", "detail": ""}'}]},
        )

        result = anthropic_client.complete_anthropic("prompt")

        assert result == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args.kwargs["url"] == "https://api.anthropic.com/v1/messages"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "claude-sonnet-4-6"
        assert body["output_config"]["format"]["type"] == "json_schema"

    def test_complete_anthropic_vertex(self, gatekeeper_config, mocker):
        gatekeeper_config.backend = GatekeeperBackend.VERTEX
        gatekeeper_config.model = "claude-sonnet-4-5@20250929"
        mocker.patch("linux_mcp_server.gatekeeper.anthropic_client.get_gcp_project", return_value="test-project")
        mocker.patch("linux_mcp_server.gatekeeper.anthropic_client.get_gcp_location", return_value="global")
        mocker.patch("linux_mcp_server.gatekeeper.anthropic_client.get_gcp_access_token", return_value="gcp-token")
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            return_value={"content": [{"type": "text", "text": '{"status": "OK"}'}]},
        )

        anthropic_client.complete_anthropic("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert "model" not in body
        assert body["anthropic_version"] == "vertex-2023-10-16"
        assert ":rawPredict" in mock_post.call_args.kwargs["url"]
