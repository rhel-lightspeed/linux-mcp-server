from fastmcp.server.dependencies import get_context
from mcp.types import InitializeRequestParams

from linux_mcp_server.config import CONFIG


RUN_SCRIPT_APP_URI = "ui://run_script_readonly_with_mcp_app/run-script-app.html"
MCP_APP_MIME_TYPE = "text/html;profile=mcp-app"
MCP_UI_EXTENSION = "io.modelcontextprotocol/ui"


def use_mcp_app_for_client(client_params: InitializeRequestParams | None = None):
    if client_params is None:
        client_params = get_context().session.client_params

    assert client_params is not None, (
        "FastMCP framework error: client_params should not be None after `initialize` is done"
    )
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


def hide_app_tools_for_client(client_params: InitializeRequestParams | None = None):
    # Versions of goose before 1.29.0 don't understand _meta.ui.visiblity, so would
    # leak our app-only tools to the model. However, they also are happy to let the
    # model call tools that aren't listed as well. So if we see such an old version
    # of goose, we strip out the app-only tools.
    if client_params is None:
        client_params = get_context().session.client_params

    assert client_params is not None, (
        "FastMCP framework error: client_params should not be None after `initialize` is done"
    )

    client_info = getattr(client_params, "clientInfo", None)
    if client_info and client_info.name and client_info.name.startswith("goose"):
        try:
            major, minor = client_info.version.split(".")[0:2]
            if (int(major), int(minor)) < (1, 29):
                return True
        except ValueError:
            return False

    return False
