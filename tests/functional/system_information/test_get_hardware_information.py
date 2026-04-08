# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import json

from utils.shell import shell


async def test_get_hw_information(mcp_session):
    """
    Test the get_hardware_information tool
    Verify the response contains the hardware information corresponding to the actual system.
    """
    response = await mcp_session.call_tool("get_hardware_information")
    assert response is not None
    data = json.loads(response.content[0].text)

    # Only the first few lines are static values, the rest can vary (eg. CPU scaling MHZ)
    actual_lscpu_output = shell("lscpu | head -n 10", silent=True).stdout.strip()
    actual_lspci_output = shell("lspci | head -n 10", silent=True).stdout.strip()

    assert actual_lscpu_output in data.get("lscpu", "")
    # lspci is returned as a list of strings in the happy path
    lspci_data = data.get("lspci", [])
    assert isinstance(lspci_data, list)
    lspci_data_str = "\n".join(lspci_data)

    for line in actual_lspci_output.splitlines():
        assert line in lspci_data_str

    # The dmidecode requires root privileges, so we skip this test for now.
    # actual_dmidecode_output = shell("dmidecode | head -n 20", silent=True).stdout.strip()
