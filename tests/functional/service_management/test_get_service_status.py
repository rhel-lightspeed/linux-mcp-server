# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
from utils.shell import shell


async def test_get_service_status_happy_path(mcp_session):
    """
    Verify that the server returns the status of a known running service.
    Uses systemd-journald as it's a core service that should always be present.
    """
    service_name = "systemd-journald"

    response = await mcp_session.call_tool("get_service_status", arguments={"service_name": service_name})
    assert response is not None

    # Verify the response contains the expected header
    assert f"=== Status of {service_name}.service ===" in response.content[0].text

    # In case the service is not running then the systemctl status command will return non zero return code.
    # So do not assert the return code here.
    actual_status = shell(f"systemctl status {service_name} | head -n 5", silent=True, doAssert=False).stdout.strip()
    assert actual_status in response.content[0].text


async def test_get_service_status_with_service_suffix(mcp_session):
    """
    Verify that the tool works when .service suffix is explicitly provided.
    """
    service_name = "systemd-journald.service"

    response = await mcp_session.call_tool("get_service_status", arguments={"service_name": service_name})
    assert response is not None

    # In case the service is not running then the systemctl status command will return non zero return code.
    # So do not assert the return code here.
    actual_status = shell(f"systemctl status {service_name} | head -n 5", silent=True, doAssert=False).stdout.strip()
    assert actual_status in response.content[0].text


async def test_get_service_status_non_existing_service(mcp_session):
    """
    Verify the response contains appropriate error when service does not exist.
    """
    response = await mcp_session.call_tool("get_service_status", arguments={"service_name": "nonexistent-service-xyz"})
    assert response is not None

    # The tool should indicate that the service was not found
    # Based on the implementation, it returns "Service 'X' not found on this system."
    assert "Service 'nonexistent-service-xyz.service' not found on this system." in response.content[0].text


async def test_get_service_status_empty_argument(mcp_session):
    """
    Verify the response contains validation error when called with empty arguments.
    """
    response = await mcp_session.call_tool("get_service_status", arguments={})
    assert response is not None
    result = response.content[0].text
    assert "1 validation error for call[get_service_status]" in result
    assert "service_name" in result
    assert "Missing required argument" in result
