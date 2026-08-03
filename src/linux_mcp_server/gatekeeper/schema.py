"""JSON schema helpers for gatekeeper structured output across LLM providers."""

from copy import deepcopy
from typing import Any


_GATEKEEPER_STATUS_VALUES = [
    "OK",
    "BAD_DESCRIPTION",
    "POLICY",
    "MODIFIES_SYSTEM",
    "UNCLEAR",
    "DANGEROUS",
    "MALICIOUS",
]


def _base_object_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": _GATEKEEPER_STATUS_VALUES,
                "description": "Gatekeeper verdict for the script.",
            },
            "detail": {
                "type": "string",
                "description": "Short explanation when status is not OK.",
            },
        },
        "required": ["status"],
        "additionalProperties": False,
    }


def _set_additional_properties_false(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)
    if result.get("type") == "object":
        result["additionalProperties"] = False
        properties = result.get("properties")
        if isinstance(properties, dict):
            for value in properties.values():
                if isinstance(value, dict):
                    _set_additional_properties_false(value)
    elif result.get("type") == "array":
        items = result.get("items")
        if isinstance(items, dict):
            _set_additional_properties_false(items)
    return result


def openai_json_schema() -> dict[str, Any]:
    """Strict JSON schema for OpenAI Responses / Chat Completions structured output."""
    return _set_additional_properties_false(_base_object_schema())


def anthropic_json_schema() -> dict[str, Any]:
    """JSON schema for Anthropic Messages API structured output."""
    return _base_object_schema()


def gemini_json_schema() -> dict[str, Any]:
    """OpenAPI 3.0 subset schema for Gemini generateContent responseSchema."""
    schema = _base_object_schema()
    # Gemini responseSchema does not use additionalProperties the same way; keep it simple.
    schema.pop("additionalProperties", None)
    return schema


def openai_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "gatekeeper_result",
            "strict": True,
            "schema": openai_json_schema(),
        },
    }


def openai_text_format() -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "name": "gatekeeper_result",
            "strict": True,
            "schema": openai_json_schema(),
        }
    }


def anthropic_output_config() -> dict[str, Any]:
    return {
        "format": {
            "type": "json_schema",
            "schema": anthropic_json_schema(),
        }
    }


def gemini_generation_config(*, temperature: float, structured_output: bool) -> dict[str, Any]:
    config: dict[str, Any] = {"temperature": temperature}
    if structured_output:
        config["responseMimeType"] = "application/json"
        config["responseSchema"] = gemini_json_schema()
    return config
