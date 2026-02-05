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

INSTRUCTIONS_FIXED = """You have access to predefined commands that inspect the system. They run standard Linux utilities and return formatted results.

## Predefined command tools

These tools map to six areas:

- **System:** hostname, OS, kernel, uptime, CPU details, memory and swap, disk usage, hardware (PCI, USB, DMI).
- **Services:** list systemd units with state; status and journal output for a given unit. Unit names get a `.service` suffix when omitted.
- **Network:** interfaces and stats, active connections, listening ports and processes.
- **Processes:** full process list and detailed info for a given PID.
- **Storage and files:** block devices; list directories or files under a path (sort by size, name, or modification time); read a file. Paths must be absolute.
- **Logs:** systemd journal with filters (unit, priority, time, transport) and tail of a specific log file. Log file paths are restricted to an allowlist (LINUX_MCP_ALLOWED_LOG_PATHS).

## Behavior

- **Remote execution:** Every tool accepts an optional `host` argument. When set, the work runs on that host over SSH instead of locally.
- **Containers:** If the `container` environment variable is set, tools refuse to run locally; a remote `host` must be used.
- **Read-only vs destructive:** All tools are marked read-only. Do not expect to be able to modify the system.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""

INSTRUCTIONS_RUN_SCRIPT = """You have access to tools that execute Python or Bash scripts you supply on the target system, for inspection or for making changes.

## Script tools

- **run_script_readonly:** Run a Python or Bash script that only inspects the system. Use for queries and data collection.
- **run_script_modify:** Run a Python or Bash script that may change files or configuration. Use only when changes are required.

## Usage

- Prefer readonly scripts when possible.
- For modifications, choose the minimal change and avoid anything that could harm stability or security.
- Describe what each script does in the description.
- Do not fetch content from the internet; use only configured repositories if installing software.
- Bash scripts run with `set -euo pipefail`; handle expected non-zero exits explicitly.
- Prefer Bash for a few shell commands and Python when logic is more involved.

## Behavior

- **Remote execution:** Every tool accepts an optional `host` argument. When set, the work runs on that host over SSH instead of locally.
- **Containers:** If the `container` environment variable is set, tools refuse to run locally; a remote `host` must be used.
- **Read-only vs destructive:** run_script_readonly is marked read-only; the modify script tool is marked destructive.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""

INSTRUCTIONS_BOTH = """You have access to two kinds of tools: predefined commands that inspect the system, and script runners that execute Python or Bash you supply.

## Predefined command tools

These tools map to six areas:

- **System:** hostname, OS, kernel, uptime, CPU details, memory and swap, disk usage, hardware (PCI, USB, DMI).
- **Services:** list systemd units with state; status and journal output for a given unit. Unit names get a `.service` suffix when omitted.
- **Network:** interfaces and stats, active connections, listening ports and processes.
- **Processes:** full process list and detailed info for a given PID.
- **Storage and files:** block devices; list directories or files under a path (sort by size, name, or modification time); read a file. Paths must be absolute.
- **Logs:** systemd journal with filters (unit, priority, time, transport) and tail of a specific log file. Log file paths are restricted to an allowlist (LINUX_MCP_ALLOWED_LOG_PATHS).

## Script tools

- **run_script_readonly:** Run a Python or Bash script that only inspects the system. Use for queries and data collection.
- **run_script_modify:** Run a Python or Bash script that may change files or configuration. Use only when changes are required.

# Usage

- Prefer fixed commands over readonly scripts when possible.
- For modifications, choose the minimal change and avoid anything that could harm stability or security.
- Describe what each script does in the description.
- Do not fetch content from the internet; use only configured repositories if installing software.
- Bash scripts run with `set -euo pipefail`; handle expected non-zero exits explicitly.
- Prefer Bash for a few shell commands and Python when logic is more involved.

## Behavior

- **Remote execution:** Every tool accepts an optional `host` argument. When set, the work runs on that host over SSH instead of locally.
- **Containers:** If the `container` environment variable is set, tools refuse to run locally; a remote `host` must be used.
- **Read-only vs destructive:** Tools that only inspect are marked read-only; the modify script tool is marked destructive.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""


kwargs = {}

match CONFIG.toolset:
    case Toolset.FIXED:
        instructions = INSTRUCTIONS_FIXED
        kwargs["exclude_tags"] = {"run_script"}
    case Toolset.RUN_SCRIPT:
        instructions = INSTRUCTIONS_RUN_SCRIPT
        kwargs["include_tags"] = {"run_script"}
    case Toolset.BOTH:
        instructions = INSTRUCTIONS_BOTH
    case _:
        assert False, f"Unknown toolset configuration: {CONFIG.toolset}"

if CONFIG.toolset != Toolset.FIXED and CONFIG.gatekeeper_model is None:
    logger.error("LINUX_MCP_GATEKEEPER_MODEL not set, this is needed for run_script tools")
    sys.exit(1)

mcp = FastMCP("linux-diagnostics", instructions=instructions, **kwargs)


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


# TODO: Dynamically inject the 'modify' tool based on user compatibility.
#
# This is a temporary implementation. The injection logic should be moved to the
# `on_initialize` handler in `DynamicDiscoveryMiddleware` once Goose starts
# providing `mcp-app` compatibility during the initialize request.
if CONFIG.use_mcp_apps:
    mcp.add_tool(run_script_modify_interactive)
    mcp.add_tool(execute_script)
else:
    mcp.add_tool(run_script_modify)


# This middleware can be used to dynamically inject tools based on client side compatibility
class DynamicDiscoveryMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)

        # Eventually, the tagging of the tools via _meta.ui.visiblity as "app" or "model" will
        # hide this tool but Goose doesn't support this yet. On the other hand, goose is happy
        # if the app calls tools we don't list at all, so we just filter out the "app" tools
        filtered_tools = [t for t in tools if "hidden_from_model" not in (t.tags)]

        return filtered_tools


def main():
    mcp.add_middleware(DynamicDiscoveryMiddleware())
    mcp.run(show_banner=False)
