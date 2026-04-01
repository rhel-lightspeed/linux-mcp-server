# Copyright Red Hat
import json

from utils.shell import shell


def format_bytes(bytes_value):
    """
    Format bytes the same way MCP server does.
    Returns format like "16.0GB", "2.5GB", "512.0MB"
    """
    value = float(bytes_value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024.0:
            return f"{value:.1f}{unit}"
        value /= 1024.0
    return f"{value:.1f}PB"


async def test_get_memory_information(mcp_session):
    """
    Verify that the server returns correct memory information.
    """

    response = await mcp_session.call_tool("get_memory_information")
    assert response is not None
    mcp_output = response.content[0].text
    data = json.loads(mcp_output)

    assert "ram" in data
    assert "total" in data["ram"]
    assert "available" in data["ram"]
    assert "used" in data["ram"]
    assert "free" in data["ram"]
    assert "swap" in data
    assert "total" in data["swap"]

    shell_output = shell("free -b -w", silent=True).stdout.strip()
    shell_lines = [line for line in shell_output.split("\n")[1:] if line.strip()]
    for line in shell_lines:
        parts = line.split()
        if parts[0] == "Mem:":
            total_ram = int(parts[1])
            # allow some deviation between `free` invocation and server's `psutil` or similar call
            assert abs(int(data["ram"]["total"]) - total_ram) < 1024 * 1024 * 10
        elif parts[0] == "Swap:":
            total_swap = int(parts[1])
            assert abs(int(data["swap"]["total"]) - total_swap) < 1024 * 1024 * 10
