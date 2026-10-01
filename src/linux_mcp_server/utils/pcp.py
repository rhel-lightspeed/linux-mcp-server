"""The PCP metrics guide, and discovery of the target system's PCP archive setup."""

import re

from importlib import resources

from fastmcp.exceptions import ToolError

import linux_mcp_server

from linux_mcp_server.commands import get_command


#: Tool serving the metric catalog and query semantics. Models otherwise invent
#: metric names from memory, and pcp_list_metrics is far too large to use as a lookup.
PCP_GUIDE_TOOL = "pcp_guide"

_PCP_GUIDE_FILE = "resources/pcp-guide.md"

#: inst [<id> or "<name>"] value "<v>"
_ARCHIVE_INSTANCE = re.compile(r'inst \[\d+ or "([^"]+)"\] value "([^"]+)"')


def read_pcp_guide() -> str:
    """The shipped metric catalog and query semantics, as markdown."""
    return resources.files(linux_mcp_server).joinpath(_PCP_GUIDE_FILE).read_text()


async def pmlogger_archive_dir(host: str) -> str:
    """The directory of archives written by this host's primary pmlogger.

    pmlogger names the directory after the host as pmcd resolves it, which is
    not always what ``hostname`` reports, so ask pmcd rather than guess.
    """
    returncode, stdout, stderr = await get_command("pcp_primary_archive").run(host=host)

    if returncode != 0:
        raise ToolError(f"Error discovering the PCP archive location: {stderr}")

    archives = dict(_ARCHIVE_INSTANCE.findall(stdout))
    archive = archives.get("primary")
    if not archive:
        raise ToolError("Primary archive location could not be discovered. Ensure pmlogger is configured.")

    return archive.rsplit("/", 1)[0]
