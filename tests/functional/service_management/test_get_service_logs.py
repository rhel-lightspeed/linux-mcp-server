# Copyright Red Hat
import os

import pytest

from utils.shell import shell


SERVICE_NAME = "systemd-journald"


@pytest.fixture(autouse=True, scope="module")
def create_fake_service_logs(service_name=SERVICE_NAME):
    """
    We need to create fake service logs for the test to work.
    It can happen that there is not enough service logs
    """
    print(f"Creating fake service logs for {service_name}...")

    # The quickest way to get authentic systemd-journald log entries is to force
    # it to flush the journal from RAM to the persistent disk journal.
    # This creates several status lines each time.
    # Simple "logger" will not work because that message is associated with the user running the logger
    # instead of the service itself.

    # Below we ignore failures so that if `systemctl kill` fails a few times, we still continue the tests
    # probably enough logs have been generated

    shell(
        "for i in {1..100}; do systemctl kill --no-ask-password -s USR1 systemd-journald || true; done",
        silent=True,
        doAssert=False,
    )


@pytest.mark.skipif(
    os.getenv("MCP_TESTS_CONTAINER_EXECUTION", "").lower() == "true",
    reason="Audit logs are not available inside container",
)
@pytest.mark.parametrize(
    "lines,expected_lines",
    [
        (None, 50),
        (-1, 50),
        (0, 50),
        (1, 1),
        (5, 5),
        (10, 10),
        (20, 20),
        (50, 50),
        (100, 100),
    ],
)
async def test_get_service_logs_lines(mcp_session, lines, expected_lines):
    """
    Verify that the server returns logs for a known service.
    Uses systemd-journald as it's a core service that should always have logs.
    When lines is None, tests the default behavior (50 lines).
    """

    arguments = {"service_name": SERVICE_NAME}
    if lines is not None:
        arguments["lines"] = lines

    response = await mcp_session.call_tool("get_service_logs", arguments=arguments)
    assert response is not None

    if lines is not None and lines < 1:
        response_text = response.content[0].text
        assert "1 validation error for call[get_service_logs]" in response_text
        assert "Input should be greater than or equal to 1" in response_text

    else:
        # Verify the response contains the expected header
        assert f"=== Last {expected_lines} log entries for {SERVICE_NAME}.service ===" in response.content[0].text

        # Verify we got at least the expected number of log lines (excluding header)
        if expected_lines > 0:
            log_lines = [line for line in response.content[0].text.splitlines() if line.strip()]
            assert len(log_lines) >= expected_lines


async def test_get_service_logs_matches_journalctl(mcp_session):
    """
    Verify the logs returned match actual journalctl output for a service.
    """
    lines = 3

    response = await mcp_session.call_tool("get_service_logs", arguments={"service_name": SERVICE_NAME, "lines": lines})
    assert response is not None

    # Get actual logs from journalctl for comparison (use LC_ALL=C to match server locale)
    actual_logs = shell(f"LC_ALL=C journalctl -u {SERVICE_NAME} -n {lines} --no-pager", silent=True).stdout.strip()

    response_text = response.content[0].text
    assert len(response_text) > 0

    # Extract log lines (skip the header and empty line from the response)
    response_lines = [line for line in response_text.splitlines()[1:] if line]

    # Verify that the log lines match
    assert response_lines == actual_logs.splitlines()


async def test_get_service_logs_non_existing_service(mcp_session):
    """
    Verify the response indicates no logs for a non-existing service.
    """
    response = await mcp_session.call_tool(
        "get_service_logs",
        arguments={"service_name": "nonexistent-service-xyz", "lines": 5},
    )
    assert response is not None

    assert "-- No entries --" in response.content[0].text


async def test_get_service_logs_empty_argument(mcp_session):
    """
    Verify the response contains validation error when called without service_name.
    """
    response = await mcp_session.call_tool("get_service_logs", arguments={})
    assert response is not None
    result = response.content[0].text
    assert "1 validation error for call[get_service_logs]" in result
    assert "service_name" in result
    assert "Missing required argument" in result


async def test_get_service_logs_with_service_suffix(mcp_session):
    """
    Verify that the tool works when .service suffix is explicitly provided.
    """
    service_name = f"{SERVICE_NAME}.service"
    lines = 5

    response = await mcp_session.call_tool("get_service_logs", arguments={"service_name": service_name, "lines": lines})
    assert response is not None

    # Verify the response contains the expected header (with .service in name)
    assert f"=== Last {lines} log entries for {service_name} ===" in response.content[0].text

    # Get actual logs from journalctl for comparison (use LC_ALL=C to match server locale)
    actual_logs = shell(f"LC_ALL=C journalctl -u {service_name} -n {lines} --no-pager", silent=True).stdout.strip()

    response_text = response.content[0].text
    assert len(response_text) > 0

    # Extract log lines (skip the header and empty line from the response)
    response_lines = [line for line in response_text.splitlines()[1:] if line]

    # Verify that the log lines match
    assert response_lines == actual_logs.splitlines()
