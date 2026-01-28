"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import sys

from importlib import resources
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware import MiddlewareContext
from mcp.types import BlobResourceContents
from mcp.types import ReadResourceRequest
from mcp.types import ReadResourceResult
from mcp.types import ServerResult
from mcp.types import TextResourceContents

import linux_mcp_server

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset
from linux_mcp_server.mcp_app import ALLOWED_UI_RESOURCE_URIS
from linux_mcp_server.mcp_app import MCP_APP_MIME_TYPE


logger = logging.getLogger("linux-mcp-server")


kwargs = {}

match CONFIG.toolset:
    case Toolset.FIXED:
        kwargs["exclude_tags"] = {"run_script"}
    case Toolset.RUN_SCRIPT:
        kwargs["include_tags"] = {"run_script"}
    case Toolset.BOTH:
        pass  # No kwargs
    case _:
        assert False, f"Unknown toolset configuration: {CONFIG.toolset}"


if CONFIG.toolset != Toolset.FIXED and CONFIG.gatekeeper_model is None:
    logger.error("LINUX_MCP_GATEKEEPER_MODEL not set, this is needed for run_script tools")
    sys.exit(1)

# Initialize FastMCP server
mcp = FastMCP(
    "linux-diagnostics",
    instructions="""
        This server provides comprehensive Linux system diagnostics and monitoring
        capabilities across six main areas:
            - system information
            - services
            - network
            - processes
            - storage and files
            - logs

        All tools support optional 'host' parameter for SSH-based remote diagnostics.
        When provided, commands execute on the remote system instead of locally.

        If running inside a container, which is indicated by the the environment variable
        "container", local execution is not allowed.

        IMPORTANT NOTES:
            - Most tools are read-only operations (indicated by readOnlyHint)
            - Log file access requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
            - Service names automatically append '.service' suffix if not provided
            - File paths must be absolute
            - Some hardware info may require elevated privileges
    """,
    **kwargs,
)

_low_level_server = mcp._mcp_server
_original_resource_request_handler = _low_level_server.request_handlers[ReadResourceRequest]


async def _read_resource_with_meta(req: ReadResourceRequest):
    uri = str(req.params.uri)
    fallback_contents: list[TextResourceContents | BlobResourceContents] = [
        TextResourceContents(uri=req.params.uri, mimeType="text/plain", text="Resource not found")
    ]

    if uri.startswith("ui://"):
        if uri in ALLOWED_UI_RESOURCE_URIS:
            filename = uri.split("/")[-1]

            # Try ui_resources first (wheel install)
            ui_resources_path = resources.files(linux_mcp_server).joinpath("ui_resources")
            resource_file = ui_resources_path.joinpath(filename)
            logger.debug(f"Checking for UI resource at: {resource_file}")

            # Check if we need to fall back to mcp-app/dist (editable install)
            if not resource_file.is_file():
                package_path = Path(linux_mcp_server.__file__).parent
                repo_root = package_path.parent.parent
                mcp_app_dist = repo_root / "mcp-app" / "dist" / filename
                logger.debug(f"Checking for UI resource at: {mcp_app_dist}")

                if mcp_app_dist.exists():
                    resource_file = mcp_app_dist
                else:
                    logger.error(f"UI resource not found: {filename}")
                    raise FileNotFoundError(f"Resource {filename} not found")

            # Read the file
            try:
                html = resource_file.read_text()
                logger.info(f"Serving UI resource from: {resource_file}")
            except Exception as e:
                logger.error(f"Failed to read UI resource from {resource_file}: {e}")
                raise

            content = TextResourceContents.model_validate(
                {
                    "uri": uri,
                    "mimeType": MCP_APP_MIME_TYPE,
                    "text": html,
                }
            )

            return ServerResult(ReadResourceResult(contents=[content]))
    else:
        if _original_resource_request_handler:
            return await _original_resource_request_handler(req)

    return ServerResult(ReadResourceResult(contents=fallback_contents))


_low_level_server.request_handlers[ReadResourceRequest] = _read_resource_with_meta


from linux_mcp_server.tools import *  # noqa: E402, F403


# This middleware can be used to dynamically inject tools based on client side compatibility
class DynamicDiscoveryMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)

        # Filter out the hidden tools
        filtered_tools = [t for t in tools if "hidden_from_agent" not in (t.tags)]
        return filtered_tools


def main():
    mcp.add_middleware(DynamicDiscoveryMiddleware())
    mcp.run(show_banner=False)
