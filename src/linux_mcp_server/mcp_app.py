from mcp.types import InitializeRequestParams

from linux_mcp_server.config import CONFIG


RUN_SCRIPT_APP_URI = "ui://run_script_readonly_with_mcp_app/run-script-app.html"
ALLOWED_UI_RESOURCE_URIS = set([RUN_SCRIPT_APP_URI])
MCP_APP_MIME_TYPE = "text/html;profile=mcp-app"
MCP_UI_EXTENSION = "io.modelcontextprotocol/ui"


def use_mcp_app_for_client(client_params: InitializeRequestParams):
    # The configuration can overwrite the MCP app support detection, so we have the flexibility to
    # manually turn the Mcp app feature on/off for developing/testing purposes.
    if CONFIG.use_mcp_apps is not None:
        return CONFIG.use_mcp_apps

    # For python-sdk -1.x, count on extensibility of protocol types - while this is being
    # removed for v2, hopefully extensions will be there properly.
    capabilities = client_params.capabilities
    extensions = getattr(capabilities, "extensions", {})
    mcp_ui_extension = extensions.get(MCP_UI_EXTENSION) or {}
    mime_types = mcp_ui_extension.get("mimeTypes") or []

    # The configuration can overwrite the MCP app support detection, so we have the flexibility to
    # manually turn the Mcp app feature on/off for developing/testing purposes.
    return MCP_APP_MIME_TYPE in mime_types
