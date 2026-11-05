from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp


@mcp.tool(
    tags={"fixed"},
    description="Get third-party packages"
)
async def get_third_party_packages(host=None):

    rc, stdout, stderr = await execute_command(
        [
            "bash",
            "-c",
            r"rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}|%{VENDOR}\n' | awk -F'|' 'BEGIN{IGNORECASE=1} $2 !~ /Red Hat/ && $1 !~ /^gpg-pubkey/'"
        ],
        host=host
    )

    return stdout