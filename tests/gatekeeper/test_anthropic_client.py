import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import anthropic_client
from linux_mcp_server.gatekeeper.anthropic_client import _anthropic_thinking_block


def test_anthropic_thinking_block_low():
    block = _anthropic_thinking_block(ReasoningEffort.LOW)
    assert block == {"type": "enabled", "budget_tokens": 4096}


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

        result = anthropic_client.complete_anthropic("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args.kwargs["url"] == "https://api.anthropic.com/v1/messages"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "claude-sonnet-4-6"
        assert body["output_config"]["format"]["type"] == "json_schema"
