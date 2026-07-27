import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
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

    async def test_complete_anthropic_adaptive_effort(self, gatekeeper_config, mocker):
        gatekeeper_config.reasoning_effort = ReasoningEffort.LOW
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
        assert body["thinking"] == {"type": "adaptive"}
        assert body["output_config"]["effort"] == "low"
        assert body["output_config"]["format"]["type"] == "json_schema"

    async def test_complete_anthropic_none_disables_thinking(self, gatekeeper_config, mocker):
        gatekeeper_config.reasoning_effort = ReasoningEffort.NONE
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"content": [{"type": "text", "text": '{"status": "OK"}'}]},
        )

        await anthropic_client.complete_anthropic("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert body["thinking"] == {"type": "disabled"}
        assert "effort" not in body["output_config"]

    async def test_complete_anthropic_unset_omits_thinking(self, gatekeeper_config, mocker):
        gatekeeper_config.reasoning_effort = None
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"content": [{"type": "text", "text": '{"status": "OK"}'}]},
        )

        await anthropic_client.complete_anthropic("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert "thinking" not in body
        assert "effort" not in body["output_config"]

    async def test_complete_anthropic_effort_without_structured_output(self, gatekeeper_config, mocker):
        gatekeeper_config.structured_output = False
        gatekeeper_config.reasoning_effort = ReasoningEffort.HIGH
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"content": [{"type": "text", "text": '{"status": "OK"}'}]},
        )

        await anthropic_client.complete_anthropic("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "claude-sonnet-4-6"
        assert body["thinking"] == {"type": "adaptive"}
        assert body["output_config"] == {"effort": "high"}

    async def test_complete_anthropic_vertex_transport_overrides(self, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.anthropic_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"content": [{"type": "text", "text": '{"status": "OK"}'}]},
        )

        await anthropic_client.complete_anthropic(
            "prompt",
            max_tokens=8000,
            url="https://aiplatform.googleapis.com/v1/projects/p/locations/global/publishers/anthropic/models/claude:rawPredict",
            headers={"Authorization": "Bearer gcp-token", "Content-Type": "application/json"},
            include_model=False,
            anthropic_version="vertex-2023-10-16",
        )

        assert ":rawPredict" in mock_post.call_args.kwargs["url"]
        body = mock_post.call_args.kwargs["body"]
        assert "model" not in body
        assert body["anthropic_version"] == "vertex-2023-10-16"
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"
        assert "x-api-key" not in mock_post.call_args.kwargs["headers"]
