"""OpenRouter Chat Completions client for the gatekeeper."""

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


OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterMessage(BaseModel):
    role: Literal["user"]
    content: str


class OpenRouterProvider(BaseModel):
    require_parameters: bool = True
    quantizations: list[str] | None = None


class OpenRouterJsonSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    strict: bool
    schema_: dict[str, Any] = Field(alias="schema")


class OpenRouterResponseFormat(BaseModel):
    type: Literal["json_schema"]
    json_schema: OpenRouterJsonSchema


class OpenRouterReasoning(BaseModel):
    enabled: bool
    effort: str | None = None


class OpenRouterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model: str
    messages: list[OpenRouterMessage]
    max_tokens: int
    temperature: float
    provider: OpenRouterProvider
    response_format: OpenRouterResponseFormat | None = None
    reasoning: OpenRouterReasoning | None = None
    chat_template_kwargs: dict[str, Any] | None = None


class OpenRouterChoiceMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str | None = None


class OpenRouterChoice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: OpenRouterChoiceMessage = Field(default_factory=OpenRouterChoiceMessage)


class OpenRouterUsage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float | None = None


class OpenRouterResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    choices: list[OpenRouterChoice] = []
    usage: OpenRouterUsage = Field(default_factory=OpenRouterUsage)


def _get_openrouter_api_key() -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter gatekeeper provider.")
    return api_key


async def complete_openrouter(
    prompt: str, *, max_tokens: int, timeout: int = DEFAULT_TIMEOUT_SECONDS
) -> GatekeeperCompletion:
    assert CONFIG.gatekeeper is not None
    configured = CONFIG.gatekeeper.openrouter.base_url if CONFIG.gatekeeper.openrouter else None
    base_url = (configured or OPENROUTER_DEFAULT_BASE_URL).rstrip("/")
    quantization = CONFIG.gatekeeper.openrouter.quantization if CONFIG.gatekeeper.openrouter else None
    template_kwargs = CONFIG.gatekeeper.openrouter.template_kwargs if CONFIG.gatekeeper.openrouter else {}
    reasoning_effort = CONFIG.gatekeeper.reasoning_effort
    request_body = OpenRouterRequest(
        model=CONFIG.gatekeeper.model,
        messages=[OpenRouterMessage(role="user", content=prompt)],
        max_tokens=max_tokens,
        temperature=CONFIG.gatekeeper.temperature,
        provider=OpenRouterProvider(quantizations=[quantization] if quantization else None),
        response_format=OpenRouterResponseFormat(
            type="json_schema",
            json_schema=OpenRouterJsonSchema(
                name="gatekeeper_result",
                strict=True,
                schema=GatekeeperResult.structured_output_schema(),
            ),
        )
        if CONFIG.gatekeeper.structured_output
        else None,
        reasoning=(
            OpenRouterReasoning(enabled=False)
            if reasoning_effort == ReasoningEffort.NONE
            else OpenRouterReasoning(enabled=True, effort=reasoning_effort.value)
            if reasoning_effort is not None
            else None
        ),
        chat_template_kwargs=template_kwargs or None,
    )
    response = await post_json(
        provider="openrouter",
        url=f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {_get_openrouter_api_key()}",
            "Content-Type": "application/json",
        },
        body=request_body.model_dump(exclude_none=True, by_alias=True),
        timeout=timeout,
    )
    parsed = OpenRouterResponse.model_validate(response)
    text = (parsed.choices[0].message.content or "").strip() if parsed.choices else ""
    return GatekeeperCompletion(
        text=text,
        prompt_tokens=parsed.usage.prompt_tokens,
        completion_tokens=parsed.usage.completion_tokens,
        usage_cost=parsed.usage.cost,
    )
