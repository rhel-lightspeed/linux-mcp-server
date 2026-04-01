# Copyright Red Hat
tools_list = [
    "get_system_information",
    "get_cpu_information",
    "get_memory_information",
    "get_disk_usage",
    "get_hardware_information",
    "list_services",
    "get_service_status",
    "get_service_logs",
    "list_processes",
    "get_process_info",
    "get_journal_logs",
    "read_log_file",
    "get_network_interfaces",
    "get_network_connections",
    "get_listening_ports",
    "list_block_devices",
    "list_directories",
    "list_files",
    "read_file",
]


async def test_list_tools(mcp_session):
    """
    Verify that the server list correctly all the available tools.
    """
    response = await mcp_session.list_tools()
    assert response is not None

    # Extract tool names from response
    actual_tools = {tool.name for tool in response.tools}
    print("Tools provided by the server:\n", actual_tools)
    expected_tools = set(tools_list)

    # Verify that the sets are equal (order doesn't matter)
    assert actual_tools == expected_tools, (
        f"Tool lists don't match. "
        f"Missing: {expected_tools - actual_tools}, "
        f"Unexpected: {actual_tools - expected_tools}"
    )
