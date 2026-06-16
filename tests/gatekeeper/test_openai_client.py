import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import OpenAIGatekeeperConfig
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import openai_client
from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError
from linux_mcp_server.gatekeeper.openai_client import _openai_reasoning_block
from linux_mcp_server.gatekeeper.openai_client import _prefers_openai_chat_completions


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("https://api.openai.com/v1", False),
        ("http://localhost:11434/v1", False),
        ("https://example.com/v1", False),
        (
            "https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi",
            True,
        ),
    ],
)
def test_prefers_openai_chat_completions(base_url, expected):
    assert _prefers_openai_chat_completions(base_url) is expected


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

    def test_complete_openai_uses_responses_api(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={
                "output_text": '{"status": "OK", "detail": ""}',
                "usage": {"input_tokens": 11, "output_tokens": 4},
            },
        )

        result = openai_client.complete_openai("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert result.prompt_tokens == 11
        assert result.completion_tokens == 4
        assert mock_post.call_args.kwargs["url"] == "https://api.openai.com/v1/responses"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "gpt-5.4"
        assert body["reasoning"] == {"effort": "low"}
        assert body["text"]["format"]["type"] == "json_schema"

    def test_complete_openai_uses_responses_api_for_ollama(self, gatekeeper_config, mocker):
        gatekeeper_config.openai = OpenAIGatekeeperConfig(base_url="http://localhost:11434/v1")
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={"output_text": '{"status": "OK", "detail": ""}'},
        )

        result = openai_client.complete_openai("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args.kwargs["url"] == "http://localhost:11434/v1/responses"

    def test_complete_openai_falls_back_to_chat_completions_on_404(self, gatekeeper_config, mocker):
        gatekeeper_config.openai = OpenAIGatekeeperConfig(base_url="https://models.example.com/v1")
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            side_effect=[
                GatekeeperHTTPError("openai", 404, "not found"),
                {
                    "choices": [{"message": {"content": '{"status": "OK", "detail": ""}'}}],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 2},
                },
            ],
        )

        result = openai_client.complete_openai("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK", "detail": ""}'
        assert result.prompt_tokens == 9
        assert result.completion_tokens == 2
        assert mock_post.call_args_list[0].kwargs["url"] == "https://models.example.com/v1/responses"
        assert mock_post.call_args_list[1].kwargs["url"] == "https://models.example.com/v1/chat/completions"
        body = mock_post.call_args_list[1].kwargs["body"]
        assert body["response_format"]["type"] == "json_schema"
        assert body["reasoning_effort"] == "low"

    def test_structured_output_disabled(self, gatekeeper_config, mocker):
        gatekeeper_config.structured_output = False
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={"output_text": '{"status": "OK"}'},
        )

        openai_client.complete_openai("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert "text" not in body

    def test_template_kwargs_on_chat_completions(self, gatekeeper_config, mocker):
        gatekeeper_config.openai = OpenAIGatekeeperConfig(
            base_url="https://models.example.com/v1",
            template_kwargs={"enable_thinking": False},
        )
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            side_effect=[
                GatekeeperHTTPError("openai", 404, "not found"),
                {"choices": [{"message": {"content": '{"status": "OK"}'}}]},
            ],
        )

        openai_client.complete_openai("prompt", max_tokens=8000)

        body = mock_post.call_args_list[1].kwargs["body"]
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
