import pytest

from linux_mcp_server.gatekeeper.http_utils import normalize_model_id


@pytest.mark.parametrize(
    "model,expected",
    [
        ("openai/gpt-5.4", "gpt-5.4"),
        ("anthropic/claude-sonnet-4-6", "claude-sonnet-4-6"),
        ("vertex_ai/gemini-3.1-pro-preview", "gemini-3.1-pro-preview"),
        ("gpt-oss-120b-maas", "gpt-oss-120b-maas"),
    ],
)
def test_normalize_model_id(model, expected):
    assert normalize_model_id(model) == expected
