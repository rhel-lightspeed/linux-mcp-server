from linux_mcp_server.gatekeeper.schema import _GATEKEEPER_STATUS_VALUES
from linux_mcp_server.gatekeeper.schema import anthropic_json_schema
from linux_mcp_server.gatekeeper.schema import gemini_json_schema
from linux_mcp_server.gatekeeper.schema import openai_json_schema
from linux_mcp_server.gatekeeper.schema import openai_response_format
from linux_mcp_server.gatekeeper.schema import openai_text_format


class TestGatekeeperSchemas:
    def test_openai_schema_is_strict(self):
        schema = openai_json_schema()
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == {"status", "detail"}
        assert schema["properties"]["status"]["enum"] == _GATEKEEPER_STATUS_VALUES

    def test_openai_response_format(self):
        response_format = openai_response_format()
        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True

    def test_openai_text_format(self):
        text_format = openai_text_format()
        assert text_format["format"]["type"] == "json_schema"
        assert text_format["format"]["name"] == "gatekeeper_result"

    def test_anthropic_schema_has_status_enum(self):
        schema = anthropic_json_schema()
        assert "status" in schema["properties"]

    def test_gemini_schema_omits_additional_properties(self):
        schema = gemini_json_schema()
        assert "additionalProperties" not in schema
