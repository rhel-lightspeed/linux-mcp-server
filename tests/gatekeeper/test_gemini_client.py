import pytest

from linux_mcp_server.config import CONFIG
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

        assert result.text == '{"status": "OK"}'
        url = mock_post.call_args.kwargs["url"]
        assert "generativelanguage.googleapis.com" in url
        assert "key=test-key" in url
        body = mock_post.call_args.kwargs["body"]
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}
