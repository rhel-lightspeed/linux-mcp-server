import importlib

from unittest.mock import AsyncMock
from unittest.mock import Mock

import litellm
import pytest

from litellm import Choices
from litellm import ModelResponse
from litellm import Usage

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper import GatekeeperResult
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.gatekeeper.check_run_script import check_run_script
from linux_mcp_server.gatekeeper.check_run_script import check_run_script_with_stats
from linux_mcp_server.gatekeeper.check_run_script import GatekeeperException
from linux_mcp_server.gatekeeper.check_run_script import get_model


# Workaround: with python-3.10, mocker.patch("linux_mcp_server.gatekeeper.check_run_script.X")
# doesn't work because it finds the imported check_run_script function rather than the module.
check_run_script_module = importlib.import_module("linux_mcp_server.gatekeeper.check_run_script")


RESULT_CASES = [
    (GatekeeperStatus.OK, "", "OK"),
    (GatekeeperStatus.BAD_DESCRIPTION, "Script does something else", "Bad description: Script does something else"),
    (GatekeeperStatus.POLICY, "Violates policy X", "Policy violation: Violates policy X"),
    (
        GatekeeperStatus.MODIFIES_SYSTEM,
        "Writes to /etc",
        "Script modifies the system and readonly is true: Writes to /etc",
    ),
    (GatekeeperStatus.UNCLEAR, "Hard to understand", "Unclear script: Hard to understand"),
    (GatekeeperStatus.DANGEROUS, "Could break the system", "Dangerous script: Could break the system"),
    (GatekeeperStatus.MALICIOUS, "Contains backdoor", "Possibly malicious script: not allowed"),
]


class TestGatekeeperResultDescription:
    @pytest.mark.parametrize("status,detail,expected_description", RESULT_CASES)
    def test_description(self, status, detail, expected_description):
        result = GatekeeperResult(status=status, detail=detail)
        assert result.description == expected_description

    @pytest.mark.parametrize("status,detail,expected_description", RESULT_CASES)
    def test_round_trip(self, status, detail, expected_description):
        """Test that we can round-trip from result -> description -> parsed result."""
        result = GatekeeperResult(status=status, detail=detail)
        parsed = GatekeeperResult.parse_from_description(result.description)

        assert parsed.status == status
        # MALICIOUS descriptions hide the original detail
        if status == GatekeeperStatus.MALICIOUS:
            assert parsed.detail == "not allowed"
        else:
            assert parsed.detail == detail

    def test_parse_from_description_unknown_prefix(self):
        with pytest.raises(ValueError, match="Unknown description prefix"):
            GatekeeperResult.parse_from_description("Unknown prefix: something")


class TestGetModel:
    def test_returns_configured_model(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", "test-model")
        assert get_model() == "test-model"

    def test_raises_when_model_not_configured(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", None)
        with pytest.raises(ValueError, match="To use run_script tools, you must set LINUX_MCP_GATEKEEPER__MODEL"):
            get_model()


class TestCheckRunScript:
    @pytest.fixture
    def mock_litellm(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", "test-model")
        mock_acompletion = mocker.patch.object(check_run_script_module, "acompletion", new_callable=AsyncMock)
        mock_get_params = mocker.patch.object(check_run_script_module, "get_supported_openai_params")
        return mock_acompletion, mock_get_params

    def _make_response(self, content: str, usage=None, finish_reason="stop") -> ModelResponse:
        message = Mock()
        message.content = content
        message.annotations = None
        choice = Mock(spec=Choices)
        choice.message = message
        choice.finish_reason = finish_reason
        response = Mock(spec=ModelResponse)
        response.model = "openai/custom/model"
        response.choices = [choice]
        response.usage = usage or Usage(prompt_tokens=1000, completion_tokens=100)
        return response

    async def test_rejects_script_with_prompt_injection_attempts(self):
        tags = ["START_OF_SCRIPT", "END_OF_SCRIPT", "START_OF_DESCRIPTION", "END_OF_DESCRIPTION"]

        for tag in tags:
            result = await check_run_script(description="test", script_type="bash", script=f"echo {tag}", readonly=True)
            assert result.status == GatekeeperStatus.MALICIOUS
            assert tag.lower() in result.detail

    @pytest.mark.parametrize(
        "structured_output,supported_params,expect_response_format",
        [
            (None, ["response_format"], True),
            (None, [""], False),
            (None, None, False),
            (False, ["response_format"], False),
            (True, [""], True),
        ],
    )
    async def test_gatekeeper_structured_output(
        self, mock_litellm, mocker, structured_output, supported_params, expect_response_format
    ):
        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = supported_params
        mock_acompletion.return_value = self._make_response('{"status": "OK", "detail": ""}')
        mocker.patch.object(CONFIG.gatekeeper, "structured_output", structured_output)

        await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

        call_kwargs = mock_acompletion.call_args.kwargs
        if expect_response_format:
            assert call_kwargs["response_format"] is GatekeeperResult
        else:
            assert "response_format" not in call_kwargs

    @pytest.mark.parametrize(
        "gatekeeper_config,expected_kwargs",
        [
            (
                GatekeeperConfig(model="openai/gpt-5.4", reasoning_effort=ReasoningEffort.LOW),
                {"model": "openai/gpt-5.4", "reasoning_effort": "low", "temperature": 0.0},
            ),
            (
                GatekeeperConfig(model="openrouter/openai/gpt-5.4", reasoning_effort=ReasoningEffort.NONE),
                {
                    "model": "openrouter/openai/gpt-5.4",
                    "reasoning": {"enabled": False},
                    "provider": {"require_parameters": True},
                    "temperature": 0.0,
                },
            ),
            (
                GatekeeperConfig(model="openrouter/openai/gpt-5.4", reasoning_effort=ReasoningEffort.LOW),
                {
                    "model": "openrouter/openai/gpt-5.4",
                    "reasoning": {"enabled": True, "effort": "low"},
                    "provider": {"require_parameters": True},
                    "temperature": 0.0,
                },
            ),
            (
                GatekeeperConfig(model="openai/gpt-5.4", template_kwargs={"enable_thinking": False}),
                {"model": "openai/gpt-5.4", "chat_template_kwargs": {"enable_thinking": False}, "temperature": 0.0},
            ),
            (
                GatekeeperConfig(model="openrouter/qwen/qwen3.5-9b", quantization="bf16"),
                {
                    "model": "openrouter/qwen/qwen3.5-9b",
                    "provider": {"require_parameters": True, "quantizations": ["bf16"]},
                    "temperature": 0.0,
                },
            ),
            (
                GatekeeperConfig(model="openai/gpt-5.4", temperature=1.0),
                {
                    "model": "openai/gpt-5.4",
                    "temperature": 1.0,
                },
            ),
        ],
    )
    async def test_gatekeeper_config_to_completion_parameters(
        self, mock_litellm, mocker, gatekeeper_config, expected_kwargs
    ):
        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = []
        mock_acompletion.return_value = self._make_response('{"status": "OK", "detail": ""}')
        mocker.patch.object(CONFIG, "gatekeeper", gatekeeper_config)

        await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

        # Add in fixed parameters
        all_expected_kwargs = expected_kwargs | {
            "max_tokens": 8000,
            "timeout": 120,
        }

        call_kwargs = mock_acompletion.call_args.kwargs
        del call_kwargs["messages"]
        assert call_kwargs == all_expected_kwargs

    async def test_missing_detail_defaults_to_empty(self, mock_litellm):
        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = ["response_format"]
        mock_acompletion.return_value = self._make_response('{"status": "OK"}')

        result = await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)
        assert result.status == GatekeeperStatus.OK
        assert result.detail == ""

    @pytest.mark.parametrize(
        "response_text",
        ["not valid json", '"just a string"', '{"status": "INVALID_STATUS"}'],
    )
    async def test_parse_errors(self, mock_litellm, response_text):
        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = None  # No response_format support
        mock_acompletion.return_value = self._make_response(response_text)

        with pytest.raises(GatekeeperException, match=r"Failed to parse gatekeeper model output"):
            await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

    async def test_timeout(self, mock_litellm):
        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = ["response_format"]
        mock_acompletion.side_effect = litellm.exceptions.Timeout(
            "Timed out", model="custom/model", llm_provider="openai"
        )

        with pytest.raises(GatekeeperException, match=r"Timeout calling gatekeeper model"):
            await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

    async def test_max_tokens(self, mock_litellm):
        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = ["response_format"]
        mock_acompletion.return_value = self._make_response('{"status": "OK"', finish_reason="length")

        with pytest.raises(GatekeeperException, match=r"Gatekeeper model output limit reached"):
            await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

    async def test_with_stats(self, mock_litellm):

        usage = Usage(prompt_tokens=1001, completion_tokens=201, cost=0.042)

        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = ["response_format"]
        mock_acompletion.return_value = self._make_response('{"status": "OK", "detail": ""}', usage)

        result, stats = await check_run_script_with_stats(
            description="test", script_type="bash", script="echo hi", readonly=True
        )
        assert result.status == GatekeeperStatus.OK
        assert result.detail == ""

        assert stats.prompt_tokens == 1001
        assert stats.completion_tokens == 201
        assert stats.cost == 0.042

    async def test_custom_cost(self, mock_litellm, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "cost", (1e-6, 4e-6))
        usage = Usage(prompt_tokens=1001, completion_tokens=201)

        mock_acompletion, mock_get_params = mock_litellm
        mock_get_params.return_value = ["response_format"]
        mock_acompletion.return_value = self._make_response('{"status": "OK", "detail": ""}', usage)

        _, stats = await check_run_script_with_stats(
            description="test", script_type="bash", script="echo hi", readonly=True
        )

        assert stats.cost == 1001 * 1e-6 + 201 * 4e-6
