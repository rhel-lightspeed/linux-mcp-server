"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import sys

from fastmcp import FastMCP

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset


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

from linux_mcp_server.tools import *  # noqa: E402, F403


def main():
    mcp.run(show_banner=False)
