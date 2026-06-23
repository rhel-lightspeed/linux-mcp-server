import asyncio
import importlib

import pytest

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import GatekeeperConfig
from linux_mcp_server.config import GatekeeperProvider
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.config import VertexAIGatekeeperConfig
from linux_mcp_server.gatekeeper import GatekeeperResult
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.gatekeeper.check_run_script import check_run_script
from linux_mcp_server.gatekeeper.check_run_script import check_run_script_with_stats
from linux_mcp_server.gatekeeper.check_run_script import GatekeeperException
from linux_mcp_server.gatekeeper.check_run_script import get_model
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion


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
        if status == GatekeeperStatus.MALICIOUS:
            assert parsed.detail == "not allowed"
        else:
            assert parsed.detail == detail

    def test_parse_from_description_unknown_prefix(self):
        with pytest.raises(ValueError, match="Unknown description prefix"):
            GatekeeperResult.parse_from_description("Unknown prefix: something")


class TestGetModel:
    def test_returns_configured_model(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", "gpt-5.4")
        assert get_model() == "gpt-5.4"

    def test_raises_when_model_not_configured(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", None)
        with pytest.raises(ValueError, match="To use run_script tools, you must set LINUX_MCP_GATEKEEPER__MODEL"):
            get_model()

    def test_accepts_openrouter_model(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", "openrouter/anthropic/claude-3.5-sonnet")
        assert get_model() == "openrouter/anthropic/claude-3.5-sonnet"


class TestCheckRunScript:
    @pytest.fixture
    def mock_llm(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "model", "gpt-5.4")
        mocker.patch.object(CONFIG.gatekeeper, "provider", GatekeeperProvider.OPENAI)

        return mocker.patch.object(
            check_run_script_module,
            "complete_gatekeeper",
            new_callable=mocker.AsyncMock,
            return_value=GatekeeperCompletion(text='{"status": "OK", "detail": ""}'),
        )

    async def test_rejects_script_with_prompt_injection_attempts(self):
        tags = ["START_OF_SCRIPT", "END_OF_SCRIPT", "START_OF_DESCRIPTION", "END_OF_DESCRIPTION"]

        for tag in tags:
            result = await check_run_script(description="test", script_type="bash", script=f"echo {tag}", readonly=True)
            assert result.status == GatekeeperStatus.MALICIOUS
            assert tag.lower() in result.detail

    async def test_calls_gatekeeper_llm(self, mock_llm):
        result = await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

        assert result.status == GatekeeperStatus.OK
        mock_llm.assert_called_once()
        prompt = mock_llm.call_args.args[0]
        assert "echo hi" in prompt
        assert "test" in prompt

    async def test_missing_detail_defaults_to_empty(self, mocker):
        mocker.patch.object(
            check_run_script_module,
            "complete_gatekeeper",
            new_callable=mocker.AsyncMock,
            return_value=GatekeeperCompletion(text='{"status": "OK"}'),
        )

        result = await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)
        assert result.status == GatekeeperStatus.OK
        assert result.detail == ""

    @pytest.mark.parametrize("response_text", ["not valid json", '"just a string"', '{"status": "INVALID_STATUS"}'])
    async def test_parse_errors(self, mocker, response_text):
        mocker.patch.object(
            check_run_script_module,
            "complete_gatekeeper",
            new_callable=mocker.AsyncMock,
            return_value=GatekeeperCompletion(text=response_text),
        )

        with pytest.raises(GatekeeperException, match=r"Failed to parse gatekeeper model output"):
            await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

    async def test_timeout(self, mocker):
        async def slow_complete(_prompt: str, **kwargs: object) -> GatekeeperCompletion:
            await asyncio.sleep(10)
            return GatekeeperCompletion(text='{"status": "OK"}')

        mocker.patch.object(
            check_run_script_module,
            "complete_gatekeeper",
            new_callable=mocker.AsyncMock,
            side_effect=slow_complete,
        )
        mocker.patch.object(check_run_script_module, "GATEKEEPER_TIMEOUT", 0.01)

        with pytest.raises(GatekeeperException, match=r"Timeout calling gatekeeper model"):
            await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

    async def test_with_stats(self, mock_llm):
        result, stats = await check_run_script_with_stats(
            description="test", script_type="bash", script="echo hi", readonly=True
        )
        assert result.status == GatekeeperStatus.OK
        assert result.detail == ""
        assert stats.latency > 0

    async def test_custom_cost(self, mocker):
        mocker.patch.object(CONFIG.gatekeeper, "cost", (1e-6, 4e-6))
        mocker.patch.object(
            check_run_script_module,
            "complete_gatekeeper",
            new_callable=mocker.AsyncMock,
            return_value=GatekeeperCompletion(
                text='{"status": "OK", "detail": ""}', prompt_tokens=100, completion_tokens=50
            ),
        )

        _, stats = await check_run_script_with_stats(
            description="test", script_type="bash", script="echo hi", readonly=True
        )

        assert stats.cost == pytest.approx(100 * 1e-6 + 50 * 4e-6)
        assert stats.cost_source == "config"

    async def test_openrouter_usage_cost(self, mocker):
        mocker.patch.object(
            check_run_script_module,
            "complete_gatekeeper",
            new_callable=mocker.AsyncMock,
            return_value=GatekeeperCompletion(
                text='{"status": "OK", "detail": ""}',
                prompt_tokens=10,
                completion_tokens=5,
                usage_cost=0.42,
            ),
        )

        _, stats = await check_run_script_with_stats(
            description="test", script_type="bash", script="echo hi", readonly=True
        )

        assert stats.prompt_tokens == 10
        assert stats.completion_tokens == 5
        assert stats.cost == 0.42
        assert stats.cost_source == "api"


class TestGatekeeperConfigIntegration:
    @pytest.fixture
    def mock_openai_post(self, mocker):
        mocker.patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False)
        return mocker.patch(
            "linux_mcp_server.gatekeeper.openai_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"output_text": '{"status": "OK", "detail": ""}'},
        )

    async def test_openai_provider_config(self, mocker, mock_openai_post):
        mocker.patch.object(
            CONFIG,
            "gatekeeper",
            GatekeeperConfig(
                provider=GatekeeperProvider.OPENAI,
                model="gpt-5.4",
                reasoning_effort=ReasoningEffort.LOW,
                structured_output=True,
                temperature=0.0,
            ),
        )

        await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

        body = mock_openai_post.call_args.kwargs["body"]
        assert body["model"] == "gpt-5.4"
        assert body["reasoning"] == {"effort": "low"}
        assert body["temperature"] == 0.0
        assert "text" in body

    async def test_vertex_ai_provider_uses_openapi_base_url(self, mocker):
        mocker.patch.dict("os.environ", {}, clear=False)
        mocker.patch(
            "linux_mcp_server.gatekeeper.gcp_auth.get_gcp_access_token",
            return_value="gcp-token",
        )
        mock_post = mocker.patch(
            "linux_mcp_server.gatekeeper.vertex_ai_client.post_json",
            new_callable=mocker.AsyncMock,
            return_value={"output_text": '{"status": "OK", "detail": ""}'},
        )
        mocker.patch.object(
            CONFIG,
            "gatekeeper",
            GatekeeperConfig(
                provider=GatekeeperProvider.VERTEX_AI,
                model="gpt-oss-120b-maas",
                vertex_ai=VertexAIGatekeeperConfig(
                    project="p",
                    base_url="https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi",
                ),
                structured_output=False,
                temperature=0.0,
            ),
        )

        await check_run_script(description="test", script_type="bash", script="echo hi", readonly=True)

        assert mock_post.call_args.kwargs["url"].endswith("/responses")
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer gcp-token"
