# Copyright Red Hat
from utils.shell import shell


async def test_get_process_info_empty_argument(mcp_session):
    """ """
    response = await mcp_session.call_tool("get_process_info")
    assert response is not None
    assert "1 validation error for call[get_process_info]" in response.content[0].text
    assert "Missing required argument" in response.content[0].text


async def test_get_process_info_non_existing_pid(mcp_session):
    """
    Verify the response contains the error message when the pid is not existing.
    """
    response = await mcp_session.call_tool(
        "get_process_info", arguments={"pid": 999999}
    )
    assert response is not None
    assert "Process with PID 999999 does not exist." in response.content[0].text


async def test_get_process_info_existing_pid(mcp_session):
    """
    Verify the response contains the process information when the pid is existing.
    """
    pid = 1
    actual_pid_info = (
        shell(f"ps -p {pid} -o pid,user,comm,args | tail -1", silent=True)
        .stdout.strip()
        .split(maxsplit=3)
    )
    pid_user = actual_pid_info[1]
    pid_comm = actual_pid_info[2]
    pid_args = actual_pid_info[3]

    response = await mcp_session.call_tool("get_process_info", arguments={"pid": pid})

    assert response is not None
    assert f"Name: {pid_comm}" in response.content[0].text
    assert "Pid: 1" in response.content[0].text
    assert pid_user in response.content[0].text
    assert pid_args in response.content[0].text
