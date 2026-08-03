import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperBackend
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import gemini_client


class TestGeminiClient:
    @pytest.fixture
    def gatekeeper_config(self, mocker):
        mocker.patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=False)
        config = GatekeeperConfig(
            provider=GatekeeperProvider.GEMINI,
            model="gemini-2.0-flash",
            reasoning_effort=ReasoningEffort.LOW,
            structured_output=True,
            temperature=0.0,
        )
        mocker.patch.object(CONFIG, "gatekeeper", config)
        return config

    def test_complete_gemini_google_ai(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            return_value={"candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}]},
        )

        result = gemini_client.complete_gemini("prompt")

        assert result == '{"status": "OK"}'
        url = mock_post.call_args.kwargs["url"]
        assert "generativelanguage.googleapis.com" in url
        assert "key=test-key" in url
        body = mock_post.call_args.kwargs["body"]
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}

    def test_complete_gemini_vertex(self, gatekeeper_config, mocker):
        gatekeeper_config.backend = GatekeeperBackend.VERTEX
        gatekeeper_config.model = "gemini-3.1-pro-preview"
        mocker.patch("linux_mcp_server.gatekeeper.gemini_client.get_gcp_project", return_value="test-project")
        mocker.patch("linux_mcp_server.gatekeeper.gemini_client.get_gcp_location", return_value="global")
        mocker.patch("linux_mcp_server.gatekeeper.gemini_client.get_gcp_access_token", return_value="gcp-token")
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            return_value={"candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}]},
        )

        gemini_client.complete_gemini("prompt")

        assert ":generateContent" in mock_post.call_args.kwargs["url"]
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"
