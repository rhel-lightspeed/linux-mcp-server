"""Anthropic Messages API client for the gatekeeper."""

import os

from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import ReasoningEffort
from linux_mcp_server.gatekeeper.check_run_script import GatekeeperResult
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion


ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicMessage(BaseModel):
    role: Literal["user"]
    content: str


class AnthropicThinking(BaseModel):
    type: Literal["adaptive", "disabled"]


class AnthropicOutputFormat(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["json_schema"]
    schema_: dict[str, Any] = Field(alias="schema")


class AnthropicOutputConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    format: AnthropicOutputFormat | None = None
    effort: str | None = None


class AnthropicRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    max_tokens: int
    messages: list[AnthropicMessage]
    temperature: float
    model: str | None = None
    thinking: AnthropicThinking | None = None
    output_config: AnthropicOutputConfig | None = None


class AnthropicContentText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["text"]
    text: str


class AnthropicUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: list[AnthropicContentText] = []
    usage: AnthropicUsage = Field(default_factory=AnthropicUsage)

    @field_validator("content", mode="before")
    @classmethod
    def _text_items_only(cls, value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict) and item.get("type") == "text"]


def _get_anthropic_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for Anthropic gatekeeper provider.")
    return api_key


async def complete_anthropic(
    prompt: str,
    *,
    max_tokens: int,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    url: str | None = None,
    headers: dict[str, str] | None = None,
    include_model: bool = True,
    anthropic_version: str | None = None,
) -> GatekeeperCompletion:
    assert CONFIG.gatekeeper is not None
    reasoning_effort = CONFIG.gatekeeper.reasoning_effort
    output_config = AnthropicOutputConfig(
        format=AnthropicOutputFormat(type="json_schema", schema=GatekeeperResult.structured_output_schema())
        if CONFIG.gatekeeper.structured_output
        else None,
        effort=reasoning_effort.value
        if reasoning_effort is not None and reasoning_effort != ReasoningEffort.NONE
        else None,
    )
    request_body = AnthropicRequest(
        max_tokens=max_tokens,
        messages=[AnthropicMessage(role="user", content=prompt)],
        temperature=CONFIG.gatekeeper.temperature,
        model=CONFIG.gatekeeper.model if include_model else None,
        thinking=(
            AnthropicThinking(type="disabled")
            if reasoning_effort == ReasoningEffort.NONE
            else AnthropicThinking(type="adaptive")
            if reasoning_effort is not None
            else None
        ),
        output_config=output_config if output_config.format is not None or output_config.effort is not None else None,
    )
    body = request_body.model_dump(exclude_none=True, by_alias=True)
    if anthropic_version is not None:
        body["anthropic_version"] = anthropic_version
    if headers is None:
        headers = {
            "x-api-key": _get_anthropic_api_key(),
            "anthropic-version": ANTHROPIC_API_VERSION,
            "Content-Type": "application/json",
        }
    response = await post_json(
        provider="anthropic",
        url=url or ANTHROPIC_API_URL,
        headers=headers,
        body=body,
        timeout=timeout,
    )
    parsed = AnthropicResponse.model_validate(response)
    return GatekeeperCompletion(
        text="".join(part.text for part in parsed.content).strip(),
        prompt_tokens=parsed.usage.input_tokens,
        completion_tokens=parsed.usage.output_tokens,
    )
