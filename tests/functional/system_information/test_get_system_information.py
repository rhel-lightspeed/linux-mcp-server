# Copyright Red Hat
import json

from utils.shell import shell


async def test_get_system_information(mcp_session, client_hostname):
    """
    Test the get_system_information tool
    Verify the response contains the hostname, architecture, and kernel version
    corresponding to the actual system.
    """
    arguments = {"host": client_hostname} if client_hostname else None
    response = await mcp_session.call_tool(
        "get_system_information", arguments=arguments
    )
    assert response is not None
    data = json.loads(response.content[0].text)

    actual_hostname = shell(
        "hostname", silent=True, host=client_hostname
    ).stdout.strip()
    actual_architecture = shell(
        "arch", silent=True, host=client_hostname
    ).stdout.strip()
    actual_kernel = shell("uname -r", silent=True, host=client_hostname).stdout.strip()

    assert actual_hostname in data.get("hostname", "")
    assert actual_architecture in data.get("arch", "")
    assert actual_kernel in data.get("kernel", "")
