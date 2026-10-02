"""Discovery of the target system's PCP archive setup."""

import re

from fastmcp.exceptions import ToolError

from linux_mcp_server.commands import get_command


#: inst [<id> or "<name>"] value "<v>"
_ARCHIVE_INSTANCE = re.compile(r'inst \[\d+ or "([^"]+)"\] value "([^"]+)"')


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
