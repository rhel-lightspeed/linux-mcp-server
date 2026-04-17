import importlib

from unittest.mock import Mock

import pytest

from litellm import Choices
from litellm import ModelResponse

from linux_mcp_server.gatekeeper import GatekeeperResult
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.gatekeeper.check_run_script import check_run_script
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
        mocker.patch.object(
            check_run_script_module,
            "CONFIG",
            gatekeeper_model="test-model",
        )
        assert get_model() == "test-model"

    def test_raises_when_model_not_configured(self, mocker):
        mocker.patch.object(
            check_run_script_module,
            "CONFIG",
            gatekeeper_model=None,
        )
        with pytest.raises(ValueError, match="must set gatekeeper_model"):
            get_model()


class TestCheckRunScript:
    @pytest.fixture
    def mock_litellm(self, mocker):
        mocker.patch.object(
            check_run_script_module,
            "CONFIG",
            gatekeeper_model="test-model",
        )
        mock_completion = mocker.patch.object(check_run_script_module, "completion")
        mock_get_params = mocker.patch.object(check_run_script_module, "get_supported_openai_params")
        return mock_completion, mock_get_params

    def _make_response(self, content: str) -> ModelResponse:
        message = Mock()
        message.content = content
        choice = Mock(spec=Choices)
        choice.message = message
        response = Mock(spec=ModelResponse)
        response.choices = [choice]
        return response

    def test_rejects_script_with_prompt_injection_attempts(self):
        tags = ["START_OF_SCRIPT", "END_OF_SCRIPT", "START_OF_DESCRIPTION", "END_OF_DESCRIPTION"]

        for tag in tags:
            result = check_run_script(description="test", script_type="bash", script=f"echo {tag}", readonly=True)
            assert result.status == GatekeeperStatus.MALICIOUS
            assert tag.lower() in result.detail

    @pytest.mark.parametrize(
        "supported_params,expect_response_format",
        [
            (["response_format", "temperature"], True),
            (["temperature"], False),
            (None, False),
        ],
    )
    def test_response_format_handling(self, mock_litellm, supported_params, expect_response_format):
        mock_completion, mock_get_params = mock_litellm
        mock_get_params.return_value = supported_params
        mock_completion.return_value = self._make_response('{"status": "OK", "detail": ""}')

        result = check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)
        assert result.status == GatekeeperStatus.OK

        call_kwargs = mock_completion.call_args.kwargs
        if expect_response_format:
            assert call_kwargs["response_format"] is GatekeeperResult
        else:
            assert call_kwargs["response_format"] is None

    @pytest.mark.parametrize(
        "response_text,error_match",
        [
            ("not valid json", "Failed to parse response"),
            ('"just a string"', "Invalid response format"),
            ('{"status": "INVALID_STATUS"}', "Bad status"),
        ],
    )
    def test_parse_errors(self, mock_litellm, response_text, error_match):
        mock_completion, mock_get_params = mock_litellm
        mock_get_params.return_value = None  # No response_format support
        mock_completion.return_value = self._make_response(response_text)

        with pytest.raises(RuntimeError, match=error_match):
            check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)
