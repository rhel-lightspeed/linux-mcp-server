import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import gemini_client
from linux_mcp_server.gatekeeper.gemini_client import _gemini_thinking_level


@pytest.mark.parametrize(
    ("effort", "expected"),
    [
        (None, None),
        (ReasoningEffort.NONE, "MINIMAL"),
        (ReasoningEffort.MINIMAL, "MINIMAL"),
        (ReasoningEffort.LOW, "LOW"),
        (ReasoningEffort.MEDIUM, "MEDIUM"),
        (ReasoningEffort.HIGH, "HIGH"),
        (ReasoningEffort.XHIGH, "HIGH"),
    ],
)
def test_gemini_thinking_level(effort, expected):
    assert _gemini_thinking_level(effort) == expected


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
