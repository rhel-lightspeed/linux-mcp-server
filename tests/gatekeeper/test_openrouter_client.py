import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import openrouter_client


class TestOpenRouterClient:
    @pytest.fixture
    def gatekeeper_config(self, mocker):
        mocker.patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}, clear=False)
        config = GatekeeperConfig(
            provider=GatekeeperProvider.OPENROUTER,
            model="openai/gpt-oss-120b",
            reasoning_effort=ReasoningEffort.LOW,
            structured_output=True,
            temperature=0.0,
        )
        mocker.patch.object(CONFIG, "gatekeeper", config)
        return config

    def test_complete_openrouter_request_body(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={
                "choices": [{"message": {"content": '{"status": "OK", "detail": ""}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001},
            },
        )

        completion = openrouter_client.complete_openrouter("prompt")

        assert completion.text == '{"status": "OK", "detail": ""}'
        assert completion.prompt_tokens == 10
        assert completion.completion_tokens == 5
        assert completion.usage_cost == 0.001
        assert mock_post.call_args.kwargs["url"] == "https://openrouter.ai/api/v1/chat/completions"
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "openai/gpt-oss-120b"
        assert body["reasoning"] == {"enabled": True, "effort": "low"}
        assert body["provider"] == {"require_parameters": True}
        assert body["response_format"]["type"] == "json_schema"

    def test_complete_openrouter_quantization(self, gatekeeper_config, mocker):
        gatekeeper_config.quantization = "fp4"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openrouter_client.complete_openrouter("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert body["provider"] == {"require_parameters": True, "quantizations": ["fp4"]}

    def test_complete_openrouter_reasoning_none(self, gatekeeper_config, mocker):
        gatekeeper_config.reasoning_effort = ReasoningEffort.NONE
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openrouter_client.complete_openrouter("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert body["reasoning"] == {"enabled": False}

    def test_complete_openrouter_legacy_model_prefix(self, gatekeeper_config, mocker):
        gatekeeper_config.model = "openrouter/google/gemma-4-26b-a4b-it"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openrouter_client.complete_openrouter("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "google/gemma-4-26b-a4b-it"

    def test_complete_openrouter_custom_base_url(self, gatekeeper_config, mocker):
        gatekeeper_config.base_url = "https://openrouter.example.com/api/v1"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openrouter_client.complete_openrouter("prompt")

        assert mock_post.call_args.kwargs["url"] == "https://openrouter.example.com/api/v1/chat/completions"

    def test_structured_output_disabled(self, gatekeeper_config, mocker):
        gatekeeper_config.structured_output = False
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openrouter_client.complete_openrouter("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert "response_format" not in body

    def test_template_kwargs(self, gatekeeper_config, mocker):
        gatekeeper_config.template_kwargs = {"enable_thinking": False}
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openrouter_client.complete_openrouter("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
