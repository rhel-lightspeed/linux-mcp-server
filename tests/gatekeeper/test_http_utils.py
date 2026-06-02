import pytest

from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.http_utils import anthropic_thinking_block
from linux_mcp_server.gatekeeper.http_utils import gemini_thinking_level
from linux_mcp_server.gatekeeper.http_utils import normalize_model_id
from linux_mcp_server.gatekeeper.http_utils import normalize_openrouter_model_id
from linux_mcp_server.gatekeeper.http_utils import openai_reasoning_block
from linux_mcp_server.gatekeeper.http_utils import openrouter_reasoning_block
from linux_mcp_server.gatekeeper.http_utils import prefers_openai_chat_completions


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


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("https://api.openai.com/v1", False),
        ("http://localhost:11434/v1", False),
        ("https://example.com/v1", False),
        (
            "https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi",
            True,
        ),
    ],
)
def test_prefers_openai_chat_completions(base_url, expected):
    assert prefers_openai_chat_completions(base_url) is expected


def test_openai_reasoning_block_none():
    assert openai_reasoning_block(None) is None
    assert openai_reasoning_block(ReasoningEffort.DEFAULT) is None


def test_openai_reasoning_block_low():
    assert openai_reasoning_block(ReasoningEffort.LOW) == {"effort": "low"}


@pytest.mark.parametrize(
    "effort,expected",
    [
        (ReasoningEffort.NONE, {"enabled": False}),
        (ReasoningEffort.LOW, {"enabled": True, "effort": "low"}),
        (ReasoningEffort.HIGH, {"enabled": True, "effort": "high"}),
    ],
)
def test_openrouter_reasoning_block(effort, expected):
    assert openrouter_reasoning_block(effort) == expected


def test_openrouter_reasoning_block_default():
    assert openrouter_reasoning_block(None) is None
    assert openrouter_reasoning_block(ReasoningEffort.DEFAULT) is None


@pytest.mark.parametrize(
    "model,expected",
    [
        ("openrouter/google/gemma-4-26b-a4b-it", "google/gemma-4-26b-a4b-it"),
        ("openai/gpt-oss-120b", "openai/gpt-oss-120b"),
    ],
)
def test_normalize_openrouter_model_id(model, expected):
    assert normalize_openrouter_model_id(model) == expected


def test_anthropic_thinking_block_low():
    block = anthropic_thinking_block(ReasoningEffort.LOW)
    assert block == {"type": "enabled", "budget_tokens": 4096}


def test_gemini_thinking_level_medium():
    assert gemini_thinking_level(ReasoningEffort.MEDIUM) == "MEDIUM"
