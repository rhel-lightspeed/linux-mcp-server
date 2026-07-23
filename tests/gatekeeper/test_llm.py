import importlib

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.gatekeeper.llm import complete_gatekeeper
from linux_mcp_server.models import GatekeeperCompletion


llm_module = importlib.import_module("linux_mcp_server.gatekeeper.llm")


class TestCompleteGatekeeper:
    async def test_routes_to_openai(self, mocker):
        mocker.patch.object(
            CONFIG,
            "gatekeeper",
            GatekeeperConfig(provider=GatekeeperProvider.OPENAI, model="gpt-5.4"),
        )
        expected = GatekeeperCompletion(text='{"status": "OK"}')
        mock_complete = mocker.patch.object(
            llm_module, "complete_openai", new_callable=mocker.AsyncMock, return_value=expected
        )
        result = await complete_gatekeeper("prompt", max_tokens=8000)
        assert result == expected
        mock_complete.assert_called_once_with("prompt", max_tokens=8000)

    async def test_routes_to_openrouter(self, mocker):
        mocker.patch.object(
            CONFIG,
            "gatekeeper",
            GatekeeperConfig(provider=GatekeeperProvider.OPENROUTER, model="openai/gpt-oss-120b"),
        )
        expected = GatekeeperCompletion(text='{"status": "OK"}', prompt_tokens=1, completion_tokens=2, usage_cost=0.5)
        mock_complete = mocker.patch.object(
            llm_module, "complete_openrouter", new_callable=mocker.AsyncMock, return_value=expected
        )
        result = await complete_gatekeeper("prompt", max_tokens=8000)
        assert result == expected
        mock_complete.assert_called_once_with("prompt", max_tokens=8000)

    async def test_routes_to_vertex_ai(self, mocker):
        mocker.patch.object(
            CONFIG,
            "gatekeeper",
            GatekeeperConfig(provider=GatekeeperProvider.VERTEX_AI, model="gemini-3.1-pro-preview"),
        )
        mock_complete = mocker.patch.object(
            llm_module,
            "complete_vertex_ai",
            new_callable=mocker.AsyncMock,
            return_value=GatekeeperCompletion(text='{"status": "OK"}'),
        )
        result = await complete_gatekeeper("prompt", max_tokens=8000)
        assert result.text == '{"status": "OK"}'
        mock_complete.assert_called_once_with("prompt", max_tokens=8000)
