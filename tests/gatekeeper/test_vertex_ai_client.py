import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import VertexAIGatekeeperConfig
from linux_mcp_server.gatekeeper import vertex_ai_client


class TestVertexAIClient:
    @pytest.fixture
    def gatekeeper_config(self, mocker):
        config = GatekeeperConfig(
            provider=GatekeeperProvider.VERTEX_AI,
            model="claude-sonnet-4-6",
            structured_output=True,
            temperature=0.0,
            vertex_ai=VertexAIGatekeeperConfig(project="test-project", location="global"),
        )
        mocker.patch.object(CONFIG, "gatekeeper", config)
        mocker.patch("linux_mcp_server.gatekeeper.vertex_ai_client.get_gcp_project", return_value="test-project")
        mocker.patch("linux_mcp_server.gatekeeper.vertex_ai_client.get_gcp_location", return_value="global")
        mocker.patch(
            "linux_mcp_server.gatekeeper.gcp_auth.get_gcp_access_token",
            return_value="gcp-token",
        )
        return config

    def test_complete_anthropic_on_vertex(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.vertex_ai_client.post_json",
            return_value={"content": [{"type": "text", "text": '{"status": "OK"}'}]},
        )

        result = vertex_ai_client.complete_vertex_ai("prompt")

        assert result.text == '{"status": "OK"}'
        body = mock_post.call_args.kwargs["body"]
        assert "model" not in body
        assert body["anthropic_version"] == "vertex-2023-10-16"
        assert ":rawPredict" in mock_post.call_args.kwargs["url"]

    def test_complete_gemini_on_vertex(self, gatekeeper_config, mocker):
        gatekeeper_config.model = "gemini-3.1-pro-preview"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.vertex_ai_client.post_json",
            return_value={"candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}]},
        )

        result = vertex_ai_client.complete_vertex_ai("prompt")

        assert result.text == '{"status": "OK"}'
        assert ":generateContent" in mock_post.call_args.kwargs["url"]
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"

    def test_complete_openai_compatible_on_vertex(self, gatekeeper_config, mocker):
        gatekeeper_config.model = "gpt-oss-120b-maas"
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.vertex_ai_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        result = vertex_ai_client.complete_vertex_ai("prompt")

        assert result.text == '{"status": "OK"}'
        assert mock_post.call_args.kwargs["url"].endswith("/chat/completions")
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"

    def test_custom_openapi_base_url(self, gatekeeper_config, mocker):
        gatekeeper_config.model = "gpt-oss-120b-maas"
        gatekeeper_config.vertex_ai = VertexAIGatekeeperConfig(
            project="test-project",
            base_url="https://custom.example.com/v1/projects/p/locations/global/endpoints/openapi",
        )
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.vertex_ai_client.post_json",
            return_value={"choices": [{"message": {"content": '{"status": "OK"}'}}]},
        )

        vertex_ai_client.complete_vertex_ai("prompt")

        assert mock_post.call_args.kwargs["url"].startswith("https://custom.example.com")
