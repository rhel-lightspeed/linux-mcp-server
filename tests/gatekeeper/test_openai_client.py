import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperBackend
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import openai_client
from linux_mcp_server.gatekeeper.http_utils import GatekeeperHTTPError


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
            return_value={"output_text": '{"status": "OK", "detail": ""}'},
        )

        result = openai_client.complete_openai("prompt")

        assert result == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args.kwargs["url"] == "https://api.openai.com/v1/responses"
        body = mock_post.call_args.kwargs["body"]
        assert body["model"] == "gpt-5.4"
        assert body["reasoning"] == {"effort": "low"}
        assert body["text"]["format"]["type"] == "json_schema"

    def test_complete_openai_uses_responses_api_for_ollama(self, gatekeeper_config, mocker):
        gatekeeper_config.base_url = "http://localhost:11434/v1"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={"output_text": '{"status": "OK", "detail": ""}'},
        )

        result = openai_client.complete_openai("prompt")

        assert result == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args.kwargs["url"] == "http://localhost:11434/v1/responses"

    def test_complete_openai_falls_back_to_chat_completions_on_404(self, gatekeeper_config, mocker):
        gatekeeper_config.base_url = "https://models.example.com/v1"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            side_effect=[
                GatekeeperHTTPError("openai", 404, "not found"),
                {"choices": [{"message": {"content": '{"status": "OK", "detail": ""}'}}]},
            ],
        )

        result = openai_client.complete_openai("prompt")

        assert result == '{"status": "OK", "detail": ""}'
        assert mock_post.call_args_list[0].kwargs["url"] == "https://models.example.com/v1/responses"
        assert mock_post.call_args_list[1].kwargs["url"] == "https://models.example.com/v1/chat/completions"
        body = mock_post.call_args_list[1].kwargs["body"]
        assert body["response_format"]["type"] == "json_schema"
        assert body["reasoning_effort"] == "low"

    def test_complete_openai_vertex_uses_gcp_token(self, gatekeeper_config, mocker):
        gatekeeper_config.backend = GatekeeperBackend.VERTEX
        gatekeeper_config.base_url = (
            "https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi"
        )
        mocker.patch(
            "linux_mcp_server.gatekeeper.gcp_auth.get_gcp_access_token",
            return_value="gcp-token",
        )
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openai_client.complete_openai("prompt")

        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["url"].endswith("/chat/completions")
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer gcp-token"

    def test_structured_output_disabled(self, gatekeeper_config, mocker):
        gatekeeper_config.structured_output = False
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={"output_text": '{"status": "OK"}'},
        )

        openai_client.complete_openai("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert "text" not in body

    def test_template_kwargs_on_chat_completions(self, gatekeeper_config, mocker):
        gatekeeper_config.base_url = (
            "https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi"
        )
        gatekeeper_config.template_kwargs = {"enable_thinking": False}
        mocker.patch(
            "linux_mcp_server.gatekeeper.gcp_auth.get_gcp_access_token",
            return_value="gcp-token",
        )
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        openai_client.complete_openai("prompt")

        body = mock_post.call_args.kwargs["body"]
        assert body["chat_template_kwargs"] == {"enable_thinking": False}
