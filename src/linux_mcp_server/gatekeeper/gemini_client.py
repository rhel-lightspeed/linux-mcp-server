"""Gemini generateContent client for the gatekeeper."""

import os

from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.check_run_script import GatekeeperResult
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion


GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

_THINKING_LEVELS = {
    ReasoningEffort.NONE: "MINIMAL",
    ReasoningEffort.MINIMAL: "MINIMAL",
    ReasoningEffort.LOW: "LOW",
    ReasoningEffort.MEDIUM: "MEDIUM",
    ReasoningEffort.HIGH: "HIGH",
    ReasoningEffort.XHIGH: "HIGH",
}


class GeminiPart(BaseModel):
    text: str


class GeminiContent(BaseModel):
    role: Literal["user"]
    parts: list[GeminiPart]


class GeminiThinkingConfig(BaseModel):
    thinkingLevel: str


class GeminiGenerationConfig(BaseModel):
    temperature: float
    maxOutputTokens: int
    responseMimeType: str | None = None
    responseSchema: dict[str, Any] | None = None
    thinkingConfig: GeminiThinkingConfig | None = None


class GeminiRequest(BaseModel):
    contents: list[GeminiContent]
    generationConfig: GeminiGenerationConfig


class GeminiResponsePart(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""


class GeminiResponseContent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    parts: list[GeminiResponsePart] = []


class GeminiCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: GeminiResponseContent = Field(default_factory=GeminiResponseContent)


class GeminiUsageMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    promptTokenCount: int = 0
    candidatesTokenCount: int = 0


class GeminiResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[GeminiCandidate] = []
    usageMetadata: GeminiUsageMetadata = Field(default_factory=GeminiUsageMetadata)


def _get_google_api_key() -> str:
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or GEMINI_API_KEY is required for Gemini direct backend.")
    return api_key


async def complete_gemini(
    prompt: str,
    *,
    max_tokens: int,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    url: str | None = None,
    headers: dict[str, str] | None = None,
) -> GatekeeperCompletion:
    assert CONFIG.gatekeeper is not None
    model = CONFIG.gatekeeper.model
    reasoning_effort = CONFIG.gatekeeper.reasoning_effort
    thinking_level = None if reasoning_effort is None else _THINKING_LEVELS.get(reasoning_effort)
    response_schema = GatekeeperResult.structured_output_schema() if CONFIG.gatekeeper.structured_output else None
    if response_schema is not None:
        # Gemini responseSchema does not use additionalProperties the same way; keep it simple.
        response_schema.pop("additionalProperties", None)
    request_body = GeminiRequest(
        contents=[GeminiContent(role="user", parts=[GeminiPart(text=prompt)])],
        generationConfig=GeminiGenerationConfig(
            temperature=CONFIG.gatekeeper.temperature,
            maxOutputTokens=max_tokens,
            responseMimeType="application/json" if CONFIG.gatekeeper.structured_output else None,
            responseSchema=response_schema,
            thinkingConfig=GeminiThinkingConfig(thinkingLevel=thinking_level) if thinking_level is not None else None,
        ),
    )
    if url is None:
        url = f"{GOOGLE_AI_BASE_URL}/models/{model}:generateContent?key={_get_google_api_key()}"
    if headers is None:
        headers = {"Content-Type": "application/json"}
    response = await post_json(
        provider="gemini",
        url=url,
        headers=headers,
        body=request_body.model_dump(exclude_none=True),
        timeout=timeout,
    )
    parsed = GeminiResponse.model_validate(response)
    parts = parsed.candidates[0].content.parts if parsed.candidates else []
    return GatekeeperCompletion(
        text="".join(part.text for part in parts).strip(),
        prompt_tokens=parsed.usageMetadata.promptTokenCount,
        completion_tokens=parsed.usageMetadata.candidatesTokenCount,
    )
