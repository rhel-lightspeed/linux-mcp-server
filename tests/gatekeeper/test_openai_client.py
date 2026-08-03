import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import OpenAIGatekeeperConfig
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import openai_client
from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError
from linux_mcp_server.gatekeeper.openai_client import OpenAIResponse


def _responses_output(text: str) -> dict:
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}


class TestOpenAIResponse:
    @pytest.mark.parametrize("output", [None, "not-a-list", {"type": "message"}, 42])
    def test_non_list_output_soft_fails_to_empty(self, output):
        parsed = OpenAIResponse.model_validate({"output": output})

        assert parsed.output == []

    def test_filters_non_message_output_items(self):
        parsed = OpenAIResponse.model_validate(
            {
                "output": [
                    {"type": "reasoning", "summary": []},
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "keep me"}],
                    },
                    {"type": "function_call", "name": "noop"},
                ]
            }
        )

        assert len(parsed.output) == 1
        assert parsed.output[0].content[0].text == "keep me"


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
                **_responses_output('{"status": "OK", "detail": ""}'),
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
            return_value=_responses_output('{"status": "OK", "detail": ""}'),
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
            return_value=_responses_output('{"status": "OK"}'),
        )

        await openai_client.complete_openai("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert "text" not in body

    async def test_complete_openai_transport_overrides(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value=_responses_output('{"status": "OK"}'),
        )

        await openai_client.complete_openai(
            "prompt",
            max_tokens=8000,
            base_url="https://vertex.example.com/openapi",
            headers={"Authorization": "Bearer gcp-token", "Content-Type": "application/json"},
        )

        assert mock_post.call_args.kwargs["url"] == "https://vertex.example.com/openapi/responses"
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"

    async def test_complete_openai_requires_api_key(self, gatekeeper_config, mocker):
        mocker.patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)

        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            await openai_client.complete_openai("prompt", max_tokens=8000)
