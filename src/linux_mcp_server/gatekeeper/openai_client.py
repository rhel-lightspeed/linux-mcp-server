"""OpenAI Responses API client for the gatekeeper."""

import os

from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from linux_mcp_server.config import CONFIG
from linux_mcp_server.gatekeeper.check_run_script import GatekeeperResult
from linux_mcp_server.gatekeeper.http_utils import DEFAULT_TIMEOUT_SECONDS
from linux_mcp_server.gatekeeper.http_utils import post_json
from linux_mcp_server.gatekeeper.llm import GatekeeperCompletion


OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIResponseOutputText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["output_text"]
    text: str


class OpenAIResponseOutputMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["message"]
    content: list[OpenAIResponseOutputText]
    id: str | None = None


class OpenAIResponseUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_tokens: int = 0
    output_tokens: int = 0


class OpenAIResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    output: list[OpenAIResponseOutputMessage] = []
    usage: OpenAIResponseUsage = Field(default_factory=OpenAIResponseUsage)

    @field_validator("output", mode="before")
    @classmethod
    def _message_items_only(cls, value: Any) -> list[Any]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict) and item.get("type") == "message"]


class OpenAIResponseFormatTextConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["json_schema"]
    name: str
    strict: bool
    schema_: dict[str, Any] = Field(alias="schema")


class OpenAIResponseTextConfig(BaseModel):
    format: OpenAIResponseFormatTextConfig


class OpenAIReasoningConfig(BaseModel):
    effort: str


class OpenAIRequest(BaseModel):
    model: str
    input: str
    max_output_tokens: int
    temperature: float
    store: bool
    reasoning: OpenAIReasoningConfig | None
    text: OpenAIResponseTextConfig | None


def _get_openai_api_key() -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI gatekeeper provider.")
    return api_key


async def complete_openai(
    prompt: str,
    *,
    max_tokens: int,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    base_url: str | None = None,
    headers: dict[str, str] | None = None,
) -> GatekeeperCompletion:
    assert CONFIG.gatekeeper is not None
    if base_url is None:
        configured = CONFIG.gatekeeper.openai.base_url if CONFIG.gatekeeper.openai else None
        base_url = (configured or os.environ.get("OPENAI_API_BASE") or OPENAI_DEFAULT_BASE_URL).rstrip("/")
    if headers is None:
        headers = {
            "Authorization": f"Bearer {_get_openai_api_key()}",
            "Content-Type": "application/json",
        }
    request_body = OpenAIRequest(
        model=CONFIG.gatekeeper.model,
        input=prompt,
        max_output_tokens=max_tokens,
        temperature=CONFIG.gatekeeper.temperature,
        store=False,
        reasoning=OpenAIReasoningConfig(effort=CONFIG.gatekeeper.reasoning_effort.value)
        if CONFIG.gatekeeper.reasoning_effort
        else None,
        text=OpenAIResponseTextConfig(
            format=OpenAIResponseFormatTextConfig(
                type="json_schema",
                name="gatekeeper_result",
                strict=True,
                schema=GatekeeperResult.structured_output_schema(),
            )
        )
        if CONFIG.gatekeeper.structured_output
        else None,
    )
    response = await post_json(
        provider="openai",
        url=f"{base_url}/responses",
        headers=headers,
        body=request_body.model_dump(exclude_none=True, by_alias=True),
        timeout=timeout,
    )
    parsed = OpenAIResponse.model_validate(response)
    return GatekeeperCompletion(
        text="".join(part.text for msg in parsed.output for part in msg.content).strip(),
        prompt_tokens=parsed.usage.input_tokens,
        completion_tokens=parsed.usage.output_tokens,
    )
