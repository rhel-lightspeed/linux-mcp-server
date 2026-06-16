import pytest

from linux_mcp_server.gatekeeper import usage
from linux_mcp_server.models import Usage


class TestUsageExtractors:
    @pytest.mark.parametrize(
        ("extractor", "response", "expected"),
        [
            (
                usage.extract_openai_chat_completions_usage,
                {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                Usage(input_tokens=10, output_tokens=5),
            ),
            (
                usage.extract_openai_responses_usage,
                {"usage": {"input_tokens": 12, "output_tokens": 3}},
                Usage(input_tokens=12, output_tokens=3),
            ),
            (
                usage.extract_anthropic_usage,
                {"usage": {"input_tokens": 20, "output_tokens": 8}},
                Usage(input_tokens=20, output_tokens=8),
            ),
            (
                usage.extract_gemini_usage,
                {"usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 2}},
                Usage(input_tokens=7, output_tokens=2),
            ),
        ],
    )
    def test_extractors(self, extractor, response, expected):
        assert extractor(response) == expected

    def test_missing_usage_returns_zeros(self):
        assert usage.extract_openai_chat_completions_usage({}) == Usage()
        assert usage.extract_anthropic_usage({"usage": "bad"}) == Usage()

    def test_openrouter_usage_includes_cost(self):
        assert usage.extract_openrouter_usage(
            {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.001}}
        ) == Usage(input_tokens=10, output_tokens=5, cost=0.001)

    def test_openrouter_usage_missing_cost(self):
        assert usage.extract_openrouter_usage({"usage": {"prompt_tokens": 1, "completion_tokens": 2}}) == Usage(
            input_tokens=1, output_tokens=2, cost=None
        )
