"""Discovery of the target system's PCP setup.

Both helpers ask the target rather than infer anything locally: the timezone
its clock runs on, and the directory its primary pmlogger writes to.
"""

import logging
import re

from fastmcp.exceptions import ToolError

from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import get_command_group
from linux_mcp_server.utils.validation import is_successful_output


logger = logging.getLogger(__name__)

#: inst [<id> or "<name>"] value "<v>"
_ARCHIVE_INSTANCE = re.compile(r'inst \[\d+ or "([^"]+)"\] value "([^"]+)"')


async def discover_timezone_name(host: str) -> str | None:
    """Read the target system's timezone name, or None if it cannot be read.

    Callers decide what an unknown timezone means for them, since guessing
    wrong is worse than saying nothing in some contexts.
    """
    try:
        returncode, stdout, _ = await get_command_group("pcp_status").commands["timezone"].run(host=host)
    except Exception:
        logger.debug("Timezone lookup failed for host %s", host, exc_info=True)
        return None

    return stdout.strip() if is_successful_output(returncode, stdout) else None


async def pmlogger_archive_dir(host: str) -> str:
    """The directory of archives written by this host's primary pmlogger.

    pmlogger names the directory after the host as pmcd resolves it, which is
    not always what ``hostname`` reports, so ask pmcd rather than guess.
    """
    returncode, stdout, stderr = await get_command("pcp_primary_archive").run(host=host)

    if returncode != 0:
        if "command not found" in stderr:
            raise ToolError("PCP is not installed on this system.")
        raise ToolError(f"Error discovering the PCP archive location: {stderr}")

    archives = dict(_ARCHIVE_INSTANCE.findall(stdout))
    archive = archives.get("primary")
    if not archive:
        raise ToolError("Primary archive location could not be discovered. Ensure pmlogger is configured.")

    return archive.rsplit("/", 1)[0]
