# Copyright Red Hat
import json
from utils.shell import shell


async def test_get_cpu_information(mcp_session):
    """
    Test the get_cpu_information tool
    Verify the response contains the CPU information corresponding to the actual system.
    """
    response = await mcp_session.call_tool("get_cpu_information")
    assert response is not None
    data = json.loads(response.content[0].text)

    actual_cpu_model = shell(
        'grep -m1 "model name" /proc/cpuinfo', silent=True
    ).stdout.strip()
    actual_cpu_model = actual_cpu_model.split(":")[1].strip()
    actual_cpu_cores = shell(
        'grep "cpu cores" /proc/cpuinfo | head -1', silent=True
    ).stdout.strip()
    actual_cpu_cores = actual_cpu_cores.split(":")[1].strip()

    assert actual_cpu_model == data.get("model")
    assert int(actual_cpu_cores) == data.get("physical_cores")
