import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import OpenAIGatekeeperConfig
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import openai_client
from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError
from linux_mcp_server.gatekeeper.openai_client import _openai_reasoning_block


def test_openai_reasoning_block_none():
    assert _openai_reasoning_block(None) is None
    assert _openai_reasoning_block(ReasoningEffort.DEFAULT) is None


def test_openai_reasoning_block_low():
    assert _openai_reasoning_block(ReasoningEffort.LOW) == {"effort": "low"}


class TestOpenAIClient:
    @pytest.fixture
    def gatekeeper_config(self, mocker):
        mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False)
        config = GatekeeperConfig(
            provider=GatekeeperProvider.OPENAI,
            model="gpt-5.4",
            reasoning_effort=ReasoningEffort.LOW,
            structured_output=True,
            temperature=0.0,
        )
        mocker.patch.object(CONFIG, "gatekeeper", config)
        return config

    async def test_complete_openai_uses_responses_api(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "output_text": '{"status": "OK", "detail": ""}',
                "usage": {"input_tokens": 11, "output_tokens": 4},
            },
        )

        result = await openai_client.complete_openai("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert result.prompt_tokens == 11
        assert result.completion_tokens == 4
        assert mock_post.call_args.kwargs["url"] == "https://api.openai.com/v1/responses"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "gpt-5.4"
        assert body["reasoning"] == {"effort": "low"}
        assert body["text"]["format"]["type"] == "json_schema"

    async def test_complete_openai_uses_responses_api_for_custom_base_url(self, gatekeeper_config, mocker):
        gatekeeper_config.openai = OpenAIGatekeeperConfig(base_url="http://localhost:11434/v1")
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"output_text": '{"status": "OK", "detail": ""}'},
        )

        result = await openai_client.complete_openai("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args.kwargs["url"] == "http://localhost:11434/v1/responses"

    async def test_complete_openai_propagates_responses_api_errors(self, gatekeeper_config, mocker):
        mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            new_callable=mocker.AsyncMock,
            side_effect=GatekeeperHTTPError("openai", 404, "not found"),
        )

        with pytest.raises(GatekeeperHTTPError, match="not found"):
            await openai_client.complete_openai("prompt", max_tokens=8000)

    async def test_structured_output_disabled(self, gatekeeper_config, mocker):
        gatekeeper_config.structured_output = False
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"output_text": '{"status": "OK"}'},
        )

        await openai_client.complete_openai("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert "text" not in body
