# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
from utils.shell import shell


async def test_list_services_happy_path(mcp_session):
    """
    Verify that the server lists correctly all the systemd services.
    Happy path test - basic invocation should return service information.
    """
    response = await mcp_session.call_tool("list_services")
    assert response is not None
    assert response.content[0].text is not None

    # Verify the response contains the expected header
    assert "=== System Services ===" in response.content[0].text

    actual_services = shell("systemctl list-units --type=service --all --no-pager", silent=True).stdout.strip()
    assert actual_services in response.content[0].text

    # Verify that some common services are present (sshd or systemd-journald are common)
    # We check for .service suffix which all services should have
    assert ".service" in response.content[0].text

    # Verify summary is present
    assert "Summary:" in response.content[0].text
    assert "services currently running" in response.content[0].text


async def test_list_services_contains_known_service(mcp_session):
    """
    Verify that a known running service appears in the list.
    Uses systemd-journald as it's a core service that should always be present.
    """
    response = await mcp_session.call_tool("list_services")
    assert response is not None

    # At least verify that we got some services in the response
    assert len(response.content[0].text) > 100  # Should be substantial output

    # Verify that the response has proper service line format
    # Services are listed with their state (running, exited, etc.)
    lines = response.content[0].text.split("\n")
    service_lines = [line for line in lines if ".service" in line]
    assert len(service_lines) > 0, "Expected at least one service in the output"

    # Verify that systemd-journald (a core service) is present
    assert "systemd-journald.service" in response.content[0].text
