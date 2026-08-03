import importlib

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.gatekeeper.llm import complete_gatekeeper
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion
from linux_mcp_server.gatekeeper.llm import resolve_provider


llm_module = importlib.import_module("linux_mcp_server.gatekeeper.llm")


class TestResolveProvider:
    def test_explicit_provider(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "provider", GatekeeperProvider.ANTHROPIC)
        mocker.patch.object(CONFIG.gatekeeper, "model", "claude-sonnet-4-6")
        assert resolve_provider() == GatekeeperProvider.ANTHROPIC

    def test_infer_openai_from_model_prefix(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "provider", None)
        mocker.patch.object(CONFIG.gatekeeper, "model", "openai/gpt-5.4")
        assert resolve_provider() == GatekeeperProvider.OPENAI

    def test_infer_gemini_from_model_prefix(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "provider", None)
        mocker.patch.object(CONFIG.gatekeeper, "model", "gemini-2.0-flash")
        assert resolve_provider() == GatekeeperProvider.GEMINI

    def test_infer_openrouter_from_model_prefix(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "provider", None)
        mocker.patch.object(CONFIG.gatekeeper, "model", "openrouter/anthropic/claude-3.5-sonnet")
        assert resolve_provider() == GatekeeperProvider.OPENROUTER


class TestCompleteGatekeeper:
    def test_routes_to_openai(self, mocker):
        mocker.patch.object(llm_module, "resolve_provider", return_value=GatekeeperProvider.OPENAI)
        mock_complete = mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.complete_openai",
            return_value='{"status": "OK"}',
        )
        result = complete_gatekeeper("prompt")
        assert result.text == '{"status": "OK"}'
        mock_complete.assert_called_once_with("prompt")

    def test_routes_to_openrouter(self, mocker):
        mocker.patch.object(llm_module, "resolve_provider", return_value=GatekeeperProvider.OPENROUTER)
        expected = GatekeeperCompletion(text='{"status": "OK"}', prompt_tokens=1, completion_tokens=2, usage_cost=0.5)
        mock_complete = mocker.patch(
            "linux_mcp_server.gatekeeper.openrouter_client.complete_openrouter",
            return_value=expected,
        )
        result = complete_gatekeeper("prompt")
        assert result == expected
        mock_complete.assert_called_once_with("prompt")
