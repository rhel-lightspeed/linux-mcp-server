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

    async def test_complete_gemini_google_ai(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}],
                "usageMetadata": {"promptTokenCount": 15, "candidatesTokenCount": 6},
            },
        )

        result = await gemini_client.complete_gemini("prompt", max_tokens=8000)

        assert result.text == '{"status": "OK"}'
        assert result.prompt_tokens == 15
        assert result.completion_tokens == 6
        url = mock_post.call_args.kwargs["url"]
        assert "generativelanguage.googleapis.com" in url
        assert "key=test-key" in url
        body = mock_post.call_args.kwargs["body"]
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "LOW"}

    async def test_complete_gemini_none_maps_to_minimal(self, gatekeeper_config, mocker):
        gatekeeper_config.reasoning_effort = ReasoningEffort.NONE
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

        await gemini_client.complete_gemini("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}

    async def test_complete_gemini_default_omits_thinking(self, gatekeeper_config, mocker):
        gatekeeper_config.reasoning_effort = None
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

        await gemini_client.complete_gemini("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert "thinkingConfig" not in body["generationConfig"]

    @pytest.mark.parametrize(
        ("effort", "expected_level"),
        [
            (ReasoningEffort.MINIMAL, "MINIMAL"),
            (ReasoningEffort.MEDIUM, "MEDIUM"),
            (ReasoningEffort.HIGH, "HIGH"),
            (ReasoningEffort.XHIGH, "HIGH"),
        ],
    )
    async def test_complete_gemini_thinking_level_mapping(self, gatekeeper_config, mocker, effort, expected_level):
        gatekeeper_config.reasoning_effort = effort
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

        await gemini_client.complete_gemini("prompt", max_tokens=8000)

        body = mock_post.call_args.kwargs["body"]
        assert body["generationConfig"]["thinkingConfig"] == {"thinkingLevel": expected_level}

    async def test_complete_gemini_transport_overrides(self, gatekeeper_config, mocker):
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.gemini_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={
                "candidates": [{"content": {"parts": [{"text": '{"status": "OK"}'}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
            },
        )

        await gemini_client.complete_gemini(
            "prompt",
            max_tokens=8000,
            url="https://aiplatform.googleapis.com/v1/projects/p/locations/global/publishers/google/models/gemini:generateContent",
            headers={"Authorization": "Bearer gcp-token", "Content-Type": "application/json"},
        )

        assert mock_post.call_args.kwargs["url"].endswith(":generateContent")
        assert "key=" not in mock_post.call_args.kwargs["url"]
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"
