import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import anthropic_client
from linux_mcp_server.gatekeeper.anthropic_client import _anthropic_thinking_block
from linux_mcp_server.gatekeeper.anthropic_client import build_messages_body


@pytest.mark.parametrize(
    ("effort", "expected"),
    [
        (None, None),
        (ReasoningEffort.NONE, {"type": "disabled"}),
        (ReasoningEffort.LOW, {"type": "adaptive"}),
        (ReasoningEffort.HIGH, {"type": "adaptive"}),
    ],
)
def test_anthropic_thinking_block(effort, expected):
    assert _anthropic_thinking_block(effort) == expected


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

    def test_build_messages_body_adaptive_effort(self, gatekeeper_config):
        gatekeeper_config.reasoning_effort = ReasoningEffort.LOW
        body = build_messages_body("prompt", include_model=True, max_tokens=8000)
        assert body["thinking"] == {"type": "adaptive"}
        assert body["output_config"]["effort"] == "low"
        assert body["output_config"]["format"]["type"] == "json_schema"

    def test_build_messages_body_none_disables_thinking(self, gatekeeper_config):
        gatekeeper_config.reasoning_effort = ReasoningEffort.NONE
        body = build_messages_body("prompt", include_model=True, max_tokens=8000)
        assert body["thinking"] == {"type": "disabled"}
        assert "effort" not in body["output_config"]

    def test_build_messages_body_unset_omits_thinking(self, gatekeeper_config):
        gatekeeper_config.reasoning_effort = None
        body = build_messages_body("prompt", include_model=True, max_tokens=8000)
        assert "thinking" not in body
        assert "effort" not in body["output_config"]

    def test_build_messages_body_effort_without_structured_output(self, gatekeeper_config):
        gatekeeper_config.structured_output = False
        gatekeeper_config.reasoning_effort = ReasoningEffort.HIGH
        body = build_messages_body("prompt", include_model=False, max_tokens=8000)
        assert "model" not in body
        assert body["thinking"] == {"type": "adaptive"}
        assert body["output_config"] == {"effort": "high"}

    async def test_complete_anthropic_direct(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "content": [{"type": "text", "text": '{"status": "OK", "detail": ""}'}],
                "usage": {"input_tokens": 30, "output_tokens": 10},
            },
        )

        result = await anthropic_client.complete_anthropic("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert result.prompt_tokens == 30
        assert result.completion_tokens == 10
        assert mock_post.call_args.kwargs["url"] == "https://api.anthropic.com/v1/messages"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "claude-sonnet-4-6"
        assert body["output_config"]["format"]["type"] == "json_schema"
